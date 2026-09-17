import { AppConfig } from '../config/AppConfig';
import {
  AccountResponse, AuthTokenResponse, ChatMessage, CreateSessionRequest, IdentifiableRecord, IndustryOption,
  InterviewKit, LearningTask, LearningTodayResponse, PracticeAttemptResponse,
  PracticeCategory, PracticeQuestion, ResumeRecord, ReviewPlan, SessionSummary
} from '../model/Models';
import { InterviewApiClient } from '../network/InterviewApiClient';
import { AuthSession } from './AuthSession';

@Observed
export class ProductStore {
  api: InterviewApiClient = new InterviewApiClient(AppConfig.apiBaseUrl);
  authenticated: boolean = false;
  busy: boolean = false;
  message: string = '';
  account: AccountResponse | null = null;
  today: LearningTodayResponse | null = null;
  plans: ReviewPlan[] = [];
  selectedPlanId: string = '';
  kits: InterviewKit[] = [];
  industries: IndustryOption[] = [];
  selectedIndustry: string = 'internet';
  interviewMode: string = 'interviewer';
  sessionId: string = '';
  messages: ChatMessage[] = [];
  resumes: ResumeRecord[] = [];
  selectedResumeId: string = '';
  sessions: SessionSummary[] = [];
  categories: PracticeCategory[] = [];
  selectedCategory: string = 'ai_application';
  questions: PracticeQuestion[] = [];
  questionIndex: number = 0;
  practiceResult: PracticeAttemptResponse | null = null;
  practiceStartedAt: number = Date.now();
  activeTask: LearningTask | null = null;
  plansHasMore: boolean = true;
  kitsHasMore: boolean = true;
  questionsHasMore: boolean = true;
  resumesHasMore: boolean = true;
  sessionsHasMore: boolean = true;
  private paging: Set<string> = new Set<string>();

  private mergeById<T extends IdentifiableRecord>(current: T[], incoming: T[]): T[] {
    const ids = new Set<string>(current.map((item: T) => item.id));
    return current.concat(incoming.filter((item: T) => !ids.has(item.id)));
  }

  async restore(token: string): Promise<void> {
    if (!token) {
      return;
    }
    this.api.setToken(token);
    try {
      this.account = await this.api.account();
      this.authenticated = true;
      await this.loadAll();
    } catch (_) {
      this.api.logout();
      await AuthSession.clear();
    }
  }

  async authenticate(email: string, password: string, displayName: string, register: boolean): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    this.message = '';
    try {
      const auth: AuthTokenResponse = register
        ? await this.api.register(email.trim(), password.trim(), displayName.trim())
        : await this.api.login(email.trim(), password.trim());
      await AuthSession.save(auth.access_token);
      this.account = await this.api.account();
      this.authenticated = true;
      await this.loadAll();
    } catch (error) {
      this.message = `登录失败：${String(error)}`;
    } finally {
      this.busy = false;
    }
  }

  async logout(): Promise<void> {
    this.api.logout();
    await AuthSession.clear();
    this.authenticated = false;
    this.account = null;
    this.today = null;
    this.plans = [];
    this.kits = [];
    this.resumes = [];
    this.sessions = [];
    this.questions = [];
    this.messages = [];
    this.sessionId = '';
    this.selectedResumeId = '';
    this.message = '';
  }

  async loadAll(): Promise<void> {
    if (!this.authenticated) return;
    await this.loadToday();
    await this.loadPlans();
    await this.loadKits();
    await this.loadPractice();
    await this.loadMine();
    try {
      this.industries = await this.api.listIndustries();
    } catch (_) {
      const fallback: IndustryOption = {
        value: 'internet', label: '互联网行业', description: '', production_signals: [], recommended_focus_areas: []
      };
      this.industries = [fallback];
    }
  }

  async loadToday(): Promise<void> {
    if (!this.authenticated) return;
    try { this.today = await this.api.learningToday(); }
    catch (error) { this.message = `加载今日任务失败：${String(error)}`; }
  }

  async runTask(task: LearningTask): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    const action = task.done ? 'reopen' : (task.status === 'todo' ? 'start' : 'complete');
    try {
      await this.api.commandLearningTask(task, action);
      this.message = '任务状态已更新';
      await this.loadToday();
    } catch (error) { this.message = `更新任务失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async openTask(task: LearningTask): Promise<void> {
    this.activeTask = task;
    if (task.link_payload?.plan_id) this.selectedPlanId = task.link_payload.plan_id;
    if (task.task_type === 'practice' && task.link_payload?.category) {
      this.selectedCategory = task.link_payload.category;
      await this.loadPractice();
    }
  }

  async loadPlans(append: boolean = false): Promise<void> {
    if (!this.authenticated) return;
    if (this.paging.has('plans') || (append && !this.plansHasMore)) return;
    this.paging.add('plans');
    try {
      if (!append) this.plansHasMore = true;
      const incoming = await this.api.listReviewPlans(20, append ? this.plans.length : 0);
      this.plans = append ? this.mergeById(this.plans, incoming) : incoming;
      this.plansHasMore = incoming.length === 20;
      if (!this.selectedPlanId) this.selectedPlanId = this.plans[0]?.id ?? '';
    } catch (error) { this.message = `加载复习计划失败：${String(error)}`; }
    finally { this.paging.delete('plans'); }
  }

  async generatePlan(role: string, days: number, focus: string): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    this.message = '正在生成计划';
    try {
      const response = await this.api.generateReviewPlan({
        title: `${role} 面试计划`, target_role: role, seniority: '高级', total_days: days,
        hours_per_day: 1.5, focus_areas: focus.split('、').filter((item: string) => Boolean(item)),
        resume_id: this.selectedResumeId || undefined, use_history: true
      });
      this.selectedPlanId = response.plan_id;
      this.message = '计划已生成';
      await this.loadPlans();
      await this.loadToday();
    } catch (error) { this.message = `生成计划失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async checkin(minutes: number, note: string): Promise<void> {
    if (!this.selectedPlanId || this.busy) return;
    this.busy = true;
    try {
      const result = await this.api.checkin(this.selectedPlanId, minutes, note);
      this.message = `打卡成功，连续 ${result.streak?.current_streak ?? 0} 天`;
      await this.loadToday();
    } catch (error) { this.message = `打卡失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async loadKits(append: boolean = false): Promise<void> {
    if (!this.authenticated) return;
    if (this.paging.has('kits') || (append && !this.kitsHasMore)) return;
    this.paging.add('kits');
    try { if (!append) this.kitsHasMore = true; const incoming = await this.api.listInterviewKits(20, append ? this.kits.length : 0); this.kits = append ? this.mergeById(this.kits, incoming) : incoming; this.kitsHasMore = incoming.length === 20; }
    catch (error) { this.message = `加载面试题单失败：${String(error)}`; }
    finally { this.paging.delete('kits'); }
  }

  async createKit(role: string, duration: number): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    try {
      const kit = await this.api.createInterviewKit({
        title: `${role} 面试题单`, target_role: role, seniority: '高级', duration_minutes: duration,
        dimensions: ['技术深度', '系统设计', '表达与协作']
      });
      this.kits = [kit, ...this.kits];
      this.message = '面试题单已创建';
    } catch (error) { this.message = `创建题单失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async startInterview(role: string): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    this.messages = [];
    try {
      const request: CreateSessionRequest = {
        offline: true, web_search: false, mode: this.interviewMode, industry: this.selectedIndustry,
        target_role: role, seniority: '高级', interview_goal: '围绕岗位能力与真实项目经历进行结构化面试。',
        focus_areas: ['项目深挖', '系统设计', '表达与协作'], resume_id: this.selectedResumeId || undefined,
        plan_task_id: this.activeTask?.task_type === 'interview' ? this.activeTask?.link_payload?.task_id : undefined
      };
      if (this.activeTask?.task_type === 'interview' && this.activeTask?.link_payload?.mode) request.mode = this.activeTask.link_payload.mode;
      if (this.activeTask?.task_type === 'interview' && this.activeTask?.link_payload?.focus) request.interview_goal = this.activeTask.link_payload.focus;
      const response = await this.api.createSession(request);
      this.sessionId = response.session_id;
      this.messages = [{ role: 'agent', text: response.message }];
      await this.loadMine();
    } catch (error) { this.message = `创建面试失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async sendInterviewMessage(text: string): Promise<void> {
    if (!text.trim() || !this.sessionId || this.busy) return;
    this.busy = true;
    this.messages = [...this.messages, { role: 'user', text: text.trim() }];
    try {
      const response = await this.api.sendMessage(this.sessionId, text.trim());
      this.messages = [...this.messages, { role: 'agent', text: response.message }];
    } catch (error) { this.message = `发送失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async loadPractice(append: boolean = false): Promise<void> {
    if (!this.authenticated) return;
    if (this.paging.has('practice') || (append && !this.questionsHasMore)) return;
    this.paging.add('practice');
    try {
      if (!append) this.questionsHasMore = true;
      if (!append) this.categories = await this.api.listPracticeCategories();
      const result = await this.api.listPracticeQuestions(this.selectedCategory, 20, append ? this.questions.length : 0);
      this.questions = append ? this.mergeById(this.questions, result.items) : result.items;
      this.questionsHasMore = result.has_more;
      const questionId = this.activeTask?.task_type === 'practice' ? this.activeTask?.link_payload?.question_id : '';
      const targetIndex = questionId ? this.questions.findIndex((question: PracticeQuestion) => question.id === questionId) : -1;
      this.questionIndex = targetIndex >= 0 ? targetIndex : 0;
      this.practiceResult = null;
      this.practiceStartedAt = Date.now();
    } catch (error) { this.message = `加载题库失败：${String(error)}`; }
    finally { this.paging.delete('practice'); }
  }

  async submitPractice(answer: string): Promise<void> {
    const question = this.questions[this.questionIndex];
    if (!question || this.busy) return;
    this.busy = true;
    try {
      const elapsed = Math.max(0, Math.round((Date.now() - this.practiceStartedAt) / 1000));
      this.practiceResult = await this.api.submitPracticeAttempt(question.id, answer, elapsed);
    } catch (error) { this.message = `提交答案失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  nextQuestion(): void {
    if (!this.questions.length) return;
    this.questionIndex = (this.questionIndex + 1) % this.questions.length;
    this.practiceResult = null;
    this.practiceStartedAt = Date.now();
    if (this.questionIndex >= this.questions.length - 6) this.loadPractice(true);
  }

  async loadMine(append: boolean = false): Promise<void> {
    if (!this.authenticated) return;
    if (this.paging.has('mine') || (append && !this.resumesHasMore && !this.sessionsHasMore)) return;
    this.paging.add('mine');
    try {
      if (!append) {
        this.resumesHasMore = true;
        this.sessionsHasMore = true;
        this.account = await this.api.account();
      }
      const incomingResumes = this.resumesHasMore ? await this.api.listResumes(20, append ? this.resumes.length : 0) : [];
      const incomingSessions = this.sessionsHasMore ? await this.api.listSessions(20, append ? this.sessions.length : 0) : [];
      this.resumes = append ? this.mergeById(this.resumes, incomingResumes) : incomingResumes;
      this.sessions = append ? this.mergeById(this.sessions, incomingSessions) : incomingSessions;
      this.resumesHasMore = incomingResumes.length === 20;
      this.sessionsHasMore = incomingSessions.length === 20;
      if (!this.selectedResumeId) this.selectedResumeId = this.resumes[0]?.id ?? '';
    } catch (error) { this.message = `加载个人资料失败：${String(error)}`; }
    finally { this.paging.delete('mine'); }
  }

  async saveResume(filename: string, text: string): Promise<void> {
    if (!text.trim() || this.busy) return;
    this.busy = true;
    try {
      const resume = await this.api.importResume(filename || 'resume.md', text.trim());
      this.selectedResumeId = resume.id;
      this.message = '简历已保存';
      await this.loadMine();
    } catch (error) { this.message = `保存简历失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async deleteResume(id: string): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    try {
      await this.api.deleteResume(id);
      if (this.selectedResumeId === id) this.selectedResumeId = '';
      this.message = '简历已删除';
      await this.loadMine();
    } catch (error) { this.message = `删除简历失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async restoreSession(id: string): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    try {
      const detail = await this.api.getSession(id);
      const restored: ChatMessage[] = [];
      detail.turns.forEach((turn) => {
        if (turn.interviewer) restored.push({ role: 'agent', text: turn.interviewer });
        if (turn.candidate) restored.push({ role: 'user', text: turn.candidate });
      });
      this.sessionId = detail.id;
      this.messages = restored;
      this.interviewMode = 'interviewer';
      this.message = '面试记录已恢复，可前往面试页继续';
    } catch (error) { this.message = `恢复面试失败：${String(error)}`; }
    finally { this.busy = false; }
  }

  async deleteSession(id: string): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    try {
      await this.api.deleteSession(id);
      if (this.sessionId === id) {
        this.sessionId = '';
        this.messages = [];
      }
      this.message = '面试记录已删除';
      await this.loadMine();
    } catch (error) { this.message = `删除面试记录失败：${String(error)}`; }
    finally { this.busy = false; }
  }
}
