import { InterviewApiClient } from '../network/InterviewApiClient';
import {
  AccountResponse,
  ChatMessage,
  CreateSessionRequest,
  IndustryOption,
  PracticeAttemptResponse,
  PracticeCategory,
  PracticeQuestion,
  ResumeRecord,
  SessionSummary,
  UserSettingsResponse
} from '../model/Models';
import { AppConfig } from '../config/AppConfig';

@Entry
@Component
struct Index {
  private api: InterviewApiClient = new InterviewApiClient(AppConfig.apiBaseUrl);

  @State healthText: string = '检查中';
  @State industries: IndustryOption[] = [];
  @State selectedIndustry: string = 'internet';
  @State messages: ChatMessage[] = [];
  @State input: string = '';
  @State sessionId: string = '';
  @State busy: boolean = false;
  @State selectedTab: string = 'chat';
  @State account: AccountResponse | null = null;
  @State settings: UserSettingsResponse | null = null;
  @State accountMessage: string = '';
  @State authPrompt: string = '';
  @State resumes: ResumeRecord[] = [];
  @State selectedResumeId: string = '';
  @State resumeDraftName: string = 'resume.md';
  @State resumeDraftText: string = '';
  @State resumeMessage: string = '';
  @State sessions: SessionSummary[] = [];
  @State historyMessage: string = '';
  @State practiceCategories: PracticeCategory[] = [];
  @State selectedPracticeCategory: string = 'ai_application';
  @State practiceQuestions: PracticeQuestion[] = [];
  @State currentPracticeIndex: number = 0;
  @State practiceAnswer: string = '';
  @State practiceResult: PracticeAttemptResponse | null = null;
  @State practiceMessage: string = '';
  @State practiceStartedAt: number = Date.now();

  aboutToAppear(): void {
    this.load();
  }

  async load(): Promise<void> {
    try {
      const status = await this.api.health();
      this.healthText = status === 'ok' ? '已连接' : '服务异常';
    } catch (error) {
      this.healthText = String(error);
    }

    try {
      this.industries = await this.api.listIndustries();
      const hasSelected = this.industries.some((item) => item.value === this.selectedIndustry);
      if (!hasSelected) {
        this.selectedIndustry = this.industries[0]?.value ?? 'internet';
      }
    } catch (_) {
      this.industries = [{ value: 'internet', label: '互联网行业', description: '', production_signals: [], recommended_focus_areas: [] }];
    }
  }

  async devLogin(): Promise<void> {
    if (this.busy) {
      return;
    }
    this.busy = true;
    this.accountMessage = '';
    try {
      await this.api.devLogin();
      this.account = await this.api.account();
      try {
        this.settings = await this.api.settings();
      } catch (_) {
        this.settings = null;
      }
      this.accountMessage = '已登录开发账号';
      this.authPrompt = '';
      await this.loadResumes();
      await this.loadSessions();
      await this.loadPractice();
    } catch (error) {
      this.accountMessage = `开发登录失败：${String(error)}`;
    } finally {
      this.busy = false;
    }
  }

  async refreshAccount(): Promise<void> {
    try {
      this.account = await this.api.account();
      try {
        this.settings = await this.api.settings();
      } catch (_) {
        this.settings = null;
      }
    } catch (_) {
      this.account = null;
    }
  }

  logout(): void {
    this.api.logout();
    this.account = null;
    this.settings = null;
    this.sessionId = '';
    this.messages = [];
    this.resumes = [];
    this.sessions = [];
    this.selectedResumeId = '';
    this.practiceQuestions = [];
    this.practiceResult = null;
    this.accountMessage = '已退出登录';
  }

  async recharge(amountCredits: string): Promise<void> {
    if (!this.requireAccount('充值积分前需要先登录账号。')) {
      return;
    }
    if (this.busy) {
      return;
    }
    this.busy = true;
    this.accountMessage = '';
    try {
      this.account = await this.api.recharge(amountCredits);
      this.accountMessage = `已充值 ${amountCredits} 积分`;
    } catch (error) {
      this.accountMessage = `充值失败：${String(error)}`;
    } finally {
      this.busy = false;
    }
  }

  async startInterview(): Promise<void> {
    if (this.busy) {
      return;
    }
    if (!this.requireAccount('开始面试前需要先登录，登录后会保存会话、简历和用量记录。')) {
      return;
    }
    this.busy = true;
    this.messages = [];
    try {
      const request: CreateSessionRequest = {
        offline: true,
        web_search: false,
        mode: 'interviewer',
        industry: this.selectedIndustry,
        target_role: 'AI 应用工程师',
        seniority: '高级',
        interview_goal: '请基于我的简历和 AI 项目经历进行真实面试。',
        focus_areas: ['简历项目深挖', 'RAG / Agent 生产化', '评测、上线、安全与观测'],
        resume_id: this.selectedResumeId || undefined
      };
      const response = await this.api.createSession(request);
      this.sessionId = response.session_id;
      this.messages = [{ role: 'agent', text: response.message }];
      await this.refreshAccount();
      await this.loadSessions();
    } catch (error) {
      this.appendSystem(`创建会话失败：${String(error)}`);
    } finally {
      this.busy = false;
    }
  }

  async send(): Promise<void> {
    const text = this.input.trim();
    if (!text || !this.sessionId || this.busy) {
      return;
    }
    if (!this.requireAccount('发送回答前需要先登录账号。')) {
      return;
    }
    this.input = '';
    this.busy = true;
    this.messages = [...this.messages, { role: 'user', text }];
    try {
      const events = await this.api.streamMessage(this.sessionId, text);
      const done = events.reverse().find((event) => event.event === 'message.done');
      const streamError = events.find((event) => event.event === 'message.error');
      if (done?.data?.['message']) {
        this.messages = [...this.messages, { role: 'agent', text: String(done.data['message']) }];
      } else if (streamError?.data?.['message']) {
        this.messages = [...this.messages, { role: 'system', text: `发送失败：${String(streamError.data['message'])}` }];
      } else {
        const response = await this.api.sendMessage(this.sessionId, text);
        this.messages = [...this.messages, { role: 'agent', text: response.message }];
      }
      await this.refreshAccount();
      await this.loadSessions();
    } catch (error) {
      this.appendSystem(`发送失败：${String(error)}`);
    } finally {
      this.busy = false;
    }
  }

  appendSystem(text: string): void {
    this.messages = [...this.messages, { role: 'system', text }];
  }

  requireAccount(message: string): boolean {
    if (this.account !== null) {
      return true;
    }
    this.authPrompt = message;
    return false;
  }

  async loadResumes(): Promise<void> {
    if (this.account === null) {
      return;
    }
    try {
      this.resumes = await this.api.listResumes();
      if (!this.selectedResumeId && this.resumes.length > 0) {
        this.selectedResumeId = this.resumes[0].id;
      }
    } catch (error) {
      this.resumeMessage = `加载简历失败：${String(error)}`;
    }
  }

  async importResumeDraft(): Promise<void> {
    const text = this.resumeDraftText.trim();
    if (!this.requireAccount('上传和保存简历前需要先登录账号。') || !text || this.busy) {
      return;
    }
    this.busy = true;
    this.resumeMessage = '';
    try {
      const resume = await this.api.importResume(this.resumeDraftName || 'resume.md', text);
      this.selectedResumeId = resume.id;
      this.resumeDraftText = '';
      this.resumeMessage = '简历已保存';
      await this.loadResumes();
    } catch (error) {
      this.resumeMessage = `上传简历失败：${String(error)}`;
    } finally {
      this.busy = false;
    }
  }

  selectResume(id: string): void {
    this.selectedResumeId = id;
    this.resumeMessage = '已选择当前简历';
  }

  async deleteResume(id: string): Promise<void> {
    if (!this.requireAccount('删除简历前需要先登录账号。')) {
      return;
    }
    try {
      await this.api.deleteResume(id);
      if (this.selectedResumeId === id) {
        this.selectedResumeId = '';
      }
      this.resumeMessage = '简历已删除';
      await this.loadResumes();
    } catch (error) {
      this.resumeMessage = `删除简历失败：${String(error)}`;
    }
  }

  async loadSessions(): Promise<void> {
    if (this.account === null) {
      return;
    }
    try {
      this.sessions = await this.api.listSessions();
    } catch (error) {
      this.historyMessage = `加载历史失败：${String(error)}`;
    }
  }

  async restoreSession(id: string): Promise<void> {
    if (!this.requireAccount('恢复历史会话前需要先登录账号。') || this.busy) {
      return;
    }
    this.busy = true;
    this.historyMessage = '';
    try {
      const detail = await this.api.getSession(id);
      const summary = this.sessions.find((item) => item.id === id);
      if (summary) {
        this.selectedResumeId = summary.resume_id ?? this.selectedResumeId;
        this.selectedIndustry = summary.industry || this.selectedIndustry;
      }
      const restored: ChatMessage[] = [];
      detail.turns.forEach((turn) => {
        if (turn.interviewer) {
          restored.push({ role: 'agent', text: turn.interviewer });
        }
        if (turn.candidate) {
          restored.push({ role: 'user', text: turn.candidate });
        }
      });
      this.sessionId = detail.id;
      this.messages = restored;
      this.historyMessage = '会话已恢复';
      this.selectedTab = 'chat';
    } catch (error) {
      this.historyMessage = `恢复会话失败：${String(error)}`;
    } finally {
      this.busy = false;
    }
  }

  async deleteSession(id: string): Promise<void> {
    if (!this.requireAccount('删除历史会话前需要先登录账号。')) {
      return;
    }
    try {
      await this.api.deleteSession(id);
      if (this.sessionId === id) {
        this.sessionId = '';
        this.messages = [];
      }
      this.historyMessage = '历史会话已删除';
      await this.loadSessions();
    } catch (error) {
      this.historyMessage = `删除历史失败：${String(error)}`;
    }
  }

  async updateDefaultMode(mode: string): Promise<void> {
    if (!this.requireAccount('更新设置前需要先登录账号。')) {
      return;
    }
    try {
      this.settings = await this.api.updateDefaultInterviewMode(mode);
      this.accountMessage = '设置已保存';
    } catch (error) {
      this.accountMessage = `保存设置失败：${String(error)}`;
    }
  }

  async loadPractice(): Promise<void> {
    if (this.account === null) {
      return;
    }
    try {
      this.practiceCategories = await this.api.listPracticeCategories();
      const hasSelected = this.practiceCategories.some((item) => item.value === this.selectedPracticeCategory);
      if (!hasSelected) {
        this.selectedPracticeCategory = this.practiceCategories[0]?.value ?? 'ai_application';
      }
      const questions = await this.api.listPracticeQuestions(this.selectedPracticeCategory);
      this.practiceQuestions = questions.items;
      this.currentPracticeIndex = 0;
      this.practiceAnswer = '';
      this.practiceResult = null;
      this.practiceStartedAt = Date.now();
    } catch (error) {
      this.practiceMessage = `加载刷题失败：${String(error)}`;
    }
  }

  async selectPracticeCategory(value: string): Promise<void> {
    this.selectedPracticeCategory = value;
    await this.loadPractice();
  }

  choosePracticeOption(value: string): void {
    this.practiceAnswer = value;
  }

  nextPracticeQuestion(): void {
    if (this.practiceQuestions.length === 0) {
      return;
    }
    this.currentPracticeIndex = (this.currentPracticeIndex + 1) % this.practiceQuestions.length;
    this.practiceAnswer = '';
    this.practiceResult = null;
    this.practiceStartedAt = Date.now();
  }

  async seedPracticeQuestions(): Promise<void> {
    if (!this.requireAccount('初始化练习样题前需要先登录账号。')) {
      return;
    }
    try {
      const result = await this.api.seedPracticeQuestions();
      this.practiceMessage = `样题已初始化：${result.total} 道`;
      await this.loadPractice();
    } catch (error) {
      this.practiceMessage = `初始化样题失败：${String(error)}`;
    }
  }

  async submitPracticeAnswer(): Promise<void> {
    const question = this.practiceQuestions[this.currentPracticeIndex];
    if (!question || !this.requireAccount('提交答案前需要先登录账号。') || this.busy) {
      return;
    }
    this.busy = true;
    this.practiceMessage = '';
    try {
      const elapsed = Math.max(0, Math.round((Date.now() - this.practiceStartedAt) / 1000));
      this.practiceResult = await this.api.submitPracticeAttempt(question.id, this.practiceAnswer, elapsed);
    } catch (error) {
      this.practiceMessage = `提交答案失败：${String(error)}`;
    } finally {
      this.busy = false;
    }
  }

  build() {
    Stack() {
      Column({ space: 12 }) {
        if (this.selectedTab === 'chat') {
          this.ChatContent()
        } else if (this.selectedTab === 'practice') {
          this.PracticeContent()
        } else if (this.selectedTab === 'resume') {
          this.ResumeContent()
        } else if (this.selectedTab === 'history') {
          this.HistoryContent()
        } else {
          this.ProfileContent()
        }

        Row({ space: 8 }) {
          Button('面试')
            .layoutWeight(1)
            .type(this.selectedTab === 'chat' ? ButtonType.Capsule : ButtonType.Normal)
            .onClick(() => {
              this.selectedTab = 'chat';
            })
          Button('简历')
            .layoutWeight(1)
            .type(this.selectedTab === 'resume' ? ButtonType.Capsule : ButtonType.Normal)
            .onClick(() => {
              this.selectedTab = 'resume';
            })
          Button('刷题')
            .layoutWeight(1)
            .type(this.selectedTab === 'practice' ? ButtonType.Capsule : ButtonType.Normal)
            .onClick(() => {
              this.selectedTab = 'practice';
            })
          Button('历史')
            .layoutWeight(1)
            .type(this.selectedTab === 'history' ? ButtonType.Capsule : ButtonType.Normal)
            .onClick(() => {
              this.selectedTab = 'history';
            })
          Button('我的')
            .layoutWeight(1)
            .type(this.selectedTab === 'profile' ? ButtonType.Capsule : ButtonType.Normal)
            .onClick(() => {
              this.selectedTab = 'profile';
            })
        }
        .width('100%')
        .padding(8)
        .backgroundColor(Color.White)
        .borderRadius(10)
      }
      .width('100%')
      .height('100%')
      .padding(16)
      .backgroundColor('#EEF4F1')

      if (this.authPrompt.length > 0) {
        Column({ space: 12 }) {
          Text('需要登录')
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
          Text(this.authPrompt)
            .fontSize(14)
            .fontColor('#4E625B')
          Row({ space: 10 }) {
            Button('稍后')
              .layoutWeight(1)
              .onClick(() => {
                this.authPrompt = '';
              })
            Button('去我的')
              .layoutWeight(1)
              .onClick(() => {
                this.authPrompt = '';
                this.selectedTab = 'profile';
              })
          }
          .width('100%')
        }
        .width('86%')
        .padding(20)
        .backgroundColor(Color.White)
        .borderRadius(14)
        .shadow({ radius: 24, color: '#33000000', offsetX: 0, offsetY: 8 })
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  ChatContent() {
    Column({ space: 12 }) {
      Row({ space: 12 }) {
        Image($r('app.media.app_icon'))
          .width(44)
          .height(44)
          .borderRadius(11)
        Column() {
          Text('Interview Agent')
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
          Text(this.healthText)
            .fontSize(12)
            .fontColor('#64756F')
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Column() {
          Text(this.account !== null ? '已登录' : '未登录')
            .fontSize(12)
            .fontColor(this.account !== null ? '#16A673' : '#C77918')
          Text(this.account !== null ? `${this.account.credit_balance} 积分` : '去我的')
            .fontSize(11)
            .fontColor('#64756F')
        }
        .alignItems(HorizontalAlign.End)
      }
      .width('100%')
      .padding(16)
      .backgroundColor(Color.White)
      .borderRadius(10)

      Column({ space: 10 }) {
        Text('行业')
          .fontSize(12)
          .fontColor('#64756F')
        Select(this.industries.map((item) => ({ value: item.value, text: item.label })))
          .selected(this.industries.findIndex((item) => item.value === this.selectedIndustry))
          .onSelect((index: number) => {
            this.selectedIndustry = this.industries[index]?.value ?? 'internet';
          })
        Button('开始面试')
          .width('100%')
          .enabled(!this.busy)
          .onClick(() => this.startInterview())
      }
      .width('100%')
      .padding(16)
      .backgroundColor(Color.White)
      .borderRadius(10)

      Scroll() {
        Column({ space: 10 }) {
          ForEach(this.messages, (message: ChatMessage) => {
            Column({ space: 4 }) {
              Text(message.role === 'user' ? '我' : message.role === 'agent' ? '面试官' : '系统')
                .fontSize(12)
                .fontColor('#64756F')
              Text(message.text)
                .fontSize(15)
                .fontColor(message.role === 'user' ? Color.White : '#14251F')
                .padding(12)
                .backgroundColor(message.role === 'user' ? '#2F63E8' : Color.White)
                .borderRadius(10)
            }
            .alignItems(message.role === 'user' ? HorizontalAlign.End : HorizontalAlign.Start)
            .width('100%')
          })
        }
        .width('100%')
      }
      .layoutWeight(1)

      Row({ space: 8 }) {
        TextInput({ placeholder: '输入你的回答', text: this.input })
          .layoutWeight(1)
          .onChange((value: string) => {
            this.input = value;
          })
        Button('发送')
          .enabled(Boolean(this.sessionId) && !this.busy && Boolean(this.input.trim()))
          .onClick(() => this.send())
      }
      .width('100%')
      .padding(12)
      .backgroundColor(Color.White)
      .borderRadius(10)
    }
    .width('100%')
    .layoutWeight(1)
  }

  @Builder
  PracticeContent() {
    Scroll() {
      Column({ space: 12 }) {
        Column({ space: 10 }) {
          Text('刷题训练')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
          Text('按题型训练，提交后查看评分、解析和复盘建议。')
            .fontSize(12)
            .fontColor('#64756F')
          Select(this.practiceCategories.map((item) => ({ value: item.value, text: item.label })))
            .selected(this.practiceCategories.findIndex((item) => item.value === this.selectedPracticeCategory))
            .onSelect((index: number) => {
              const category = this.practiceCategories[index];
              if (category) {
                this.selectPracticeCategory(category.value);
              }
            })
          Row({ space: 8 }) {
            Button('刷新题库')
              .layoutWeight(1)
              .enabled(!this.busy)
              .onClick(() => this.loadPractice())
            Button('初始化样题')
              .layoutWeight(1)
              .enabled(!this.busy)
              .onClick(() => this.seedPracticeQuestions())
          }
          .width('100%')
          if (this.practiceMessage) {
            Text(this.practiceMessage)
              .fontSize(12)
              .fontColor(this.practiceMessage.includes('失败') ? '#D43B3B' : '#16A673')
          }
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)

        if (this.practiceQuestions.length > 0) {
          Column({ space: 12 }) {
            Text(`${this.currentPracticeIndex + 1} / ${this.practiceQuestions.length}`)
              .fontSize(12)
              .fontColor('#64756F')
            Text(this.practiceQuestions[this.currentPracticeIndex].prompt)
              .fontSize(16)
              .fontWeight(FontWeight.Medium)
              .fontColor('#14251F')
            if (this.practiceQuestions[this.currentPracticeIndex].choices.length > 0) {
              ForEach(this.practiceQuestions[this.currentPracticeIndex].choices, (choice: string, index: number) => {
                Button(`${String.fromCharCode(65 + index)}. ${choice}`)
                  .width('100%')
                  .type(this.practiceAnswer === String.fromCharCode(65 + index) ? ButtonType.Capsule : ButtonType.Normal)
                  .onClick(() => this.choosePracticeOption(String.fromCharCode(65 + index)))
              }, (choice: string, index: number) => `${index}-${choice}`)
            } else {
              TextArea({ placeholder: '写下你的答题思路', text: this.practiceAnswer })
                .height(140)
                .onChange((value: string) => {
                  this.practiceAnswer = value;
                })
            }
            Row({ space: 8 }) {
              Button('下一题')
                .layoutWeight(1)
                .onClick(() => this.nextPracticeQuestion())
              Button('提交答案')
                .layoutWeight(1)
                .enabled(!this.busy)
                .onClick(() => this.submitPracticeAnswer())
            }
            .width('100%')
          }
          .width('100%')
          .padding(16)
          .backgroundColor(Color.White)
          .borderRadius(10)
        } else {
          Column({ space: 8 }) {
            Text('暂无题目')
              .fontSize(16)
              .fontWeight(FontWeight.Bold)
            Text('可以初始化样题，或切换训练类型后刷新。')
              .fontSize(12)
              .fontColor('#64756F')
          }
          .width('100%')
          .padding(16)
          .backgroundColor(Color.White)
          .borderRadius(10)
        }

        if (this.practiceResult !== null) {
          Column({ space: 8 }) {
            Text(`${this.practiceResult.score} 分`)
              .fontSize(28)
              .fontWeight(FontWeight.Bold)
              .fontColor('#0F8F8F')
            Text(this.practiceResult.feedback)
              .fontSize(13)
              .fontColor('#14251F')
            this.InfoRow('参考答案', this.practiceResult.reference_answer || '-')
            this.InfoRow('解析', this.practiceResult.explanation || '-')
            Text('复盘建议')
              .fontSize(13)
              .fontWeight(FontWeight.Bold)
            ForEach(this.practiceResult.suggestions, (suggestion: string) => {
              Text(`- ${suggestion}`)
                .fontSize(12)
                .fontColor('#64756F')
            }, (suggestion: string) => suggestion)
          }
          .width('100%')
          .padding(16)
          .backgroundColor(Color.White)
          .borderRadius(10)
        }
      }
      .width('100%')
    }
    .layoutWeight(1)
  }

  @Builder
  ResumeContent() {
    Scroll() {
      Column({ space: 12 }) {
        Column({ space: 10 }) {
          Text('导入简历')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
          TextInput({ placeholder: '文件名', text: this.resumeDraftName })
            .onChange((value: string) => {
              this.resumeDraftName = value;
            })
          TextArea({ placeholder: '粘贴 Markdown / 文本简历', text: this.resumeDraftText })
            .height(140)
            .onChange((value: string) => {
              this.resumeDraftText = value;
            })
          Button('保存简历')
            .width('100%')
            .enabled(!this.busy && Boolean(this.resumeDraftText.trim()))
            .onClick(() => this.importResumeDraft())
          if (this.resumeMessage) {
            Text(this.resumeMessage)
              .fontSize(12)
              .fontColor(this.resumeMessage.includes('失败') ? '#D43B3B' : '#16A673')
          }
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)

        Column({ space: 8 }) {
          Text('当前简历')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
          Text(this.resumes.find((item) => item.id === this.selectedResumeId)?.filename ?? '暂未选择')
            .fontSize(13)
            .fontColor('#64756F')
          Button('刷新简历库')
            .width('100%')
            .onClick(() => this.loadResumes())
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)

        ForEach(this.resumes, (resume: ResumeRecord) => {
          Column({ space: 8 }) {
            Row() {
              Text(resume.filename)
                .fontSize(15)
                .fontWeight(FontWeight.Bold)
                .layoutWeight(1)
              if (resume.id === this.selectedResumeId) {
                Text('当前')
                  .fontSize(12)
                  .fontColor('#16A673')
              }
            }
            .width('100%')
            Text(resume.summary || '暂无摘要')
              .fontSize(12)
              .fontColor('#64756F')
              .maxLines(3)
            Row({ space: 8 }) {
              Button('选择')
                .layoutWeight(1)
                .onClick(() => this.selectResume(resume.id))
              Button('删除')
                .layoutWeight(1)
                .onClick(() => this.deleteResume(resume.id))
            }
            .width('100%')
          }
          .width('100%')
          .padding(16)
          .backgroundColor(Color.White)
          .borderRadius(10)
        }, (resume: ResumeRecord) => resume.id)
      }
      .width('100%')
    }
    .layoutWeight(1)
  }

  @Builder
  HistoryContent() {
    Scroll() {
      Column({ space: 12 }) {
        Column({ space: 8 }) {
          Text('历史会话')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
          Text(this.historyMessage || '可恢复最近的面试上下文继续对话。')
            .fontSize(12)
            .fontColor(this.historyMessage.includes('失败') ? '#D43B3B' : '#64756F')
          Button('刷新历史')
            .width('100%')
            .onClick(() => this.loadSessions())
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)

        ForEach(this.sessions, (session: SessionSummary) => {
          Column({ space: 8 }) {
            Row() {
              Text(session.target_role)
                .fontSize(15)
                .fontWeight(FontWeight.Bold)
                .layoutWeight(1)
              Text(session.status)
                .fontSize(12)
                .fontColor('#64756F')
            }
            .width('100%')
            Text(`${session.mode === 'candidate' ? 'Agent 回答我' : 'Agent 面试我'} · ${session.seniority} · ${session.updated_at}`)
              .fontSize(12)
              .fontColor('#64756F')
            Row({ space: 8 }) {
              Button('恢复')
                .layoutWeight(1)
                .onClick(() => this.restoreSession(session.id))
              Button('删除')
                .layoutWeight(1)
                .onClick(() => this.deleteSession(session.id))
            }
            .width('100%')
          }
          .width('100%')
          .padding(16)
          .backgroundColor(Color.White)
          .borderRadius(10)
        }, (session: SessionSummary) => session.id)
      }
      .width('100%')
    }
    .layoutWeight(1)
  }

  @Builder
  ProfileContent() {
    Scroll() {
      Column({ space: 12 }) {
        Row({ space: 14 }) {
          Image($r('app.media.app_icon'))
            .width(58)
            .height(58)
            .borderRadius(12)
          Column({ space: 4 }) {
            Text(this.account?.display_name ?? '未登录')
              .fontSize(22)
              .fontWeight(FontWeight.Bold)
            Text(this.account?.email ?? this.account?.user_id ?? '登录后保存简历、会话和用量记录')
              .fontSize(12)
              .fontColor('#64756F')
          }
          .layoutWeight(1)
          .alignItems(HorizontalAlign.Start)
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)

        Column({ space: 12 }) {
          Text('权益')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
          Row({ space: 10 }) {
            this.MetricBox('剩余试用', this.account !== null ? String(this.account.trial_uses_remaining) : '-')
            this.MetricBox('积分余额', this.account?.credit_balance ?? '-')
          }
          Row({ space: 8 }) {
            Button('充 10')
              .layoutWeight(1)
              .enabled(this.account !== null && !this.busy)
              .onClick(() => this.recharge('10'))
            Button('充 50')
              .layoutWeight(1)
              .enabled(this.account !== null && !this.busy)
              .onClick(() => this.recharge('50'))
            Button('充 100')
              .layoutWeight(1)
              .enabled(this.account !== null && !this.busy)
              .onClick(() => this.recharge('100'))
          }
          .width('100%')
          if (this.accountMessage) {
            Text(this.accountMessage)
              .fontSize(12)
              .fontColor(this.accountMessage.includes('失败') ? '#D43B3B' : '#16A673')
          }
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)

        Column({ space: 8 }) {
          Text('账号信息')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
          this.InfoRow('租户', this.account?.tenant_id ?? '-')
          this.InfoRow('用户', this.account?.user_id ?? '-')
          this.InfoRow('平台', this.account?.platform ?? '-')
          this.InfoRow('服务', this.healthText)
          this.InfoRow('默认模式', this.settings?.default_interview_mode === 'candidate' ? 'Agent 回答我' : 'Agent 面试我')
          Row({ space: 8 }) {
            Button('默认面试我')
              .layoutWeight(1)
              .onClick(() => this.updateDefaultMode('interviewer'))
            Button('默认回答我')
              .layoutWeight(1)
              .onClick(() => this.updateDefaultMode('candidate'))
          }
          .width('100%')
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)

        Column({ space: 10 }) {
          Button(this.account !== null ? '刷新账户' : '开发登录')
            .width('100%')
            .enabled(!this.busy)
            .onClick(() => {
              if (this.account !== null) {
                this.refreshAccount();
              } else {
                this.devLogin();
              }
            })
          if (this.account !== null) {
            Button('退出登录')
              .width('100%')
              .onClick(() => this.logout())
          }
        }
        .width('100%')
        .padding(16)
        .backgroundColor(Color.White)
        .borderRadius(10)
      }
      .width('100%')
    }
    .layoutWeight(1)
  }

  @Builder
  MetricBox(label: string, value: string) {
    Column({ space: 6 }) {
      Text(label)
        .fontSize(12)
        .fontColor('#64756F')
      Text(value)
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
        .fontColor('#0F8F8F')
    }
    .layoutWeight(1)
    .padding(12)
    .backgroundColor('#F7FAF8')
    .borderRadius(10)
  }

  @Builder
  InfoRow(label: string, value: string) {
    Row() {
      Text(label)
        .fontSize(13)
        .fontColor('#64756F')
        .layoutWeight(1)
      Text(value)
        .fontSize(13)
        .fontColor('#14251F')
        .textAlign(TextAlign.End)
        .layoutWeight(2)
    }
    .width('100%')
  }
}
