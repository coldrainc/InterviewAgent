import { EmptyState, PageHeader, SectionTitle } from '../components/ProductComponents';
import { ChatMessage, InterviewKit } from '../model/Models';
import { ProductStore } from '../state/ProductStore';

@Component
export struct InterviewPage {
  @ObjectLink store: ProductStore;
  @State role: string = 'AI 应用工程师';
  @State input: string = '';

  build() {
    Column({ space: 14 }) {
      PageHeader('Interview', '面试训练', '在候选人与面试官视角间切换')
      Row({ space: 8 }) {
        Button('我是候选人').layoutWeight(1).type(this.store.interviewMode === 'interviewer' ? ButtonType.Capsule : ButtonType.Normal)
          .onClick(() => this.store.interviewMode = 'interviewer')
        Button('我是面试官').layoutWeight(1).type(this.store.interviewMode === 'candidate' ? ButtonType.Capsule : ButtonType.Normal)
          .onClick(() => this.store.interviewMode = 'candidate')
      }.width('100%')
      if (this.store.interviewMode === 'candidate') {
        this.InterviewerWorkspace()
      } else {
        this.CandidateWorkspace()
      }
    }.width('100%').height('100%').padding(18).backgroundColor('#F3F6F4')
  }

  @Builder CandidateWorkspace() {
    Column({ space: 12 }) {
      Row({ space: 8 }) {
        TextInput({ placeholder: '目标岗位', text: this.role }).layoutWeight(1).onChange((value: string) => this.role = value)
        Button(this.store.sessionId ? '重新开始' : '开始').enabled(!this.store.busy).onClick(() => this.store.startInterview(this.role))
      }.width('100%')
      Scroll() {
        Column({ space: 10 }) {
          if (!this.store.messages.length) {
            EmptyState('准备好后开始', 'AI 面试官会逐步追问，并根据你的回答调整难度。')
          }
          ForEach(this.store.messages, (message: ChatMessage, index: number) => {
            Column({ space: 3 }) {
              Text(message.role === 'user' ? '我' : '面试官').fontSize(11).fontColor('#65746F')
              Text(message.text).fontSize(14).fontColor(message.role === 'user' ? Color.White : '#15241F')
                .padding(12).backgroundColor(message.role === 'user' ? '#315BE8' : Color.White).borderRadius(8)
            }.alignItems(message.role === 'user' ? HorizontalAlign.End : HorizontalAlign.Start).width('100%')
          }, (_item: ChatMessage, index: number) => `${index}`)
        }.width('100%')
      }.layoutWeight(1).width('100%')
      Row({ space: 8 }) {
        TextInput({ placeholder: '输入你的回答', text: this.input }).layoutWeight(1).onChange((value: string) => this.input = value)
        Button('发送').enabled(Boolean(this.store.sessionId) && Boolean(this.input.trim()) && !this.store.busy)
          .onClick(() => { const text = this.input; this.input = ''; this.store.sendInterviewMessage(text); })
      }.width('100%')
    }.layoutWeight(1).width('100%')
  }

  @Builder InterviewerWorkspace() {
    Scroll() {
      Column({ space: 12 }) {
        Column({ space: 10 }) {
          TextInput({ placeholder: '招聘岗位', text: this.role }).onChange((value: string) => this.role = value)
          Button('生成结构化面试题单').width('100%').enabled(!this.store.busy).onClick(() => this.store.createKit(this.role, 45))
        }.width('100%').padding(16).backgroundColor('#E9EEFF').borderRadius(8)
        SectionTitle('我的题单', `${this.store.kits.length} 份`)
        if (!this.store.kits.length) {
          EmptyState('还没有面试题单', '输入岗位后生成，题目会覆盖技术、系统设计与沟通能力。')
        }
        ForEach(this.store.kits, (kit: InterviewKit, index: number) => {
          Column({ space: 6 }) {
            Text(kit.title).fontSize(16).fontWeight(FontWeight.Bold)
            Text(`${kit.target_role} · ${kit.duration_minutes} 分钟 · ${kit.questions?.length ?? 0} 题`).fontSize(12).fontColor('#65746F')
          }.alignItems(HorizontalAlign.Start).width('100%').padding(15).backgroundColor(Color.White).borderRadius(8)
            .onAppear(() => { if (index >= this.store.kits.length - 6) this.store.loadKits(true); })
        }, (kit: InterviewKit) => kit.id)
      }.width('100%')
    }.layoutWeight(1).width('100%')
  }
}
