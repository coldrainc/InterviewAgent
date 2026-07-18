import { InterviewApiClient } from '../network/InterviewApiClient';
import { AccountResponse, ChatMessage, CreateSessionRequest, IndustryOption } from '../model/Models';
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
  @State accountMessage: string = '';
  @State authPrompt: string = '';

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
      this.selectedIndustry = this.industries[0]?.value ?? 'internet';
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
      this.accountMessage = '已登录开发账号';
      this.authPrompt = '';
    } catch (error) {
      this.accountMessage = `开发登录失败：${String(error)}`;
    } finally {
      this.busy = false;
    }
  }

  async refreshAccount(): Promise<void> {
    try {
      this.account = await this.api.account();
    } catch (_) {
      this.account = null;
    }
  }

  logout(): void {
    this.api.logout();
    this.account = null;
    this.sessionId = '';
    this.messages = [];
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
        focus_areas: ['简历项目深挖', 'RAG / Agent 生产化', '评测、上线、安全与观测']
      };
      const response = await this.api.createSession(request);
      this.sessionId = response.session_id;
      this.messages = [{ role: 'agent', text: response.message }];
      await this.refreshAccount();
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
      const reply = String(done?.data?.['message'] ?? '流式响应结束，但未返回消息。');
      this.messages = [...this.messages, { role: 'agent', text: reply }];
      await this.refreshAccount();
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

  build() {
    Stack() {
      Column({ space: 12 }) {
        if (this.selectedTab === 'chat') {
          this.ChatContent()
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
