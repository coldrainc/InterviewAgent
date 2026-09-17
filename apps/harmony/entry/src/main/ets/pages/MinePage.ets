import { PageHeader, SectionTitle } from '../components/ProductComponents';
import { ResumeRecord, SessionSummary } from '../model/Models';
import { ProductStore } from '../state/ProductStore';

@Component
export struct MinePage {
  @ObjectLink store: ProductStore;
  @State filename: string = 'resume.md';
  @State resumeText: string = '';

  build() {
    Scroll() {
      Column({ space: 14 }) {
        PageHeader('Mine', '我的', '管理简历、面试记录与账号')
        Row({ space: 12 }) {
          Text((this.store.account?.display_name ?? '我').slice(0, 1)).fontSize(20).fontColor(Color.White)
            .width(48).height(48).textAlign(TextAlign.Center).backgroundColor('#27735F').borderRadius(24)
          Column({ space: 4 }) {
            Text(this.store.account?.display_name ?? '已登录').fontSize(17).fontWeight(FontWeight.Bold)
            Text(this.store.account?.email ?? '学习进度已安全同步').fontSize(12).fontColor('#65746F')
          }.alignItems(HorizontalAlign.Start)
          Blank()
          Text(`${this.store.account?.credit_balance ?? '0'} 积分`).fontSize(12).fontColor('#27735F')
        }.width('100%').padding(17).backgroundColor(Color.White).borderRadius(8)
        SectionTitle('简历', `${this.store.resumes.length} 份`)
        Column({ space: 9 }) {
          TextInput({ placeholder: '文件名', text: this.filename }).onChange((value: string) => this.filename = value)
          TextArea({ placeholder: '粘贴简历文本', text: this.resumeText }).height(120).onChange((value: string) => this.resumeText = value)
          Button('保存为新简历').width('100%').enabled(Boolean(this.resumeText.trim()) && !this.store.busy)
            .onClick(() => { this.store.saveResume(this.filename, this.resumeText); this.resumeText = ''; })
        }.width('100%').padding(15).backgroundColor(Color.White).borderRadius(8)
        ForEach(this.store.resumes, (resume: ResumeRecord, index: number) => {
          Row({ space: 10 }) {
            Column({ space: 3 }) {
              Text(resume.filename).fontSize(14).fontWeight(FontWeight.Medium)
              Text(resume.summary || '已安全保存').fontSize(11).fontColor('#65746F').maxLines(1)
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Radio({ value: resume.id, group: 'resume' }).checked(this.store.selectedResumeId === resume.id)
              .onChange((checked: boolean) => { if (checked) this.store.selectedResumeId = resume.id; })
            Button('删除').fontSize(11).type(ButtonType.Normal).enabled(!this.store.busy)
              .onClick(() => this.store.deleteResume(resume.id))
          }.width('100%').padding(13).backgroundColor(Color.White).borderRadius(8)
            .onAppear(() => { if (index >= this.store.resumes.length - 6) this.store.loadMine(true); })
        }, (resume: ResumeRecord) => resume.id)
        SectionTitle('最近面试', `${this.store.sessions.length} 场`)
        ForEach(this.store.sessions, (session: SessionSummary, index: number) => {
          Row({ space: 8 }) {
            Column({ space: 4 }) {
              Text(session.target_role || '模拟面试').fontSize(14).fontWeight(FontWeight.Medium)
              Text(`${session.mode === 'candidate' ? '面试官视角' : '候选人视角'} · ${session.status}`).fontSize(11).fontColor('#65746F')
            }.alignItems(HorizontalAlign.Start).layoutWeight(1)
            Button('继续').fontSize(11).enabled(!this.store.busy).onClick(() => this.store.restoreSession(session.id))
            Button('删除').fontSize(11).type(ButtonType.Normal).enabled(!this.store.busy).onClick(() => this.store.deleteSession(session.id))
          }.width('100%').padding(13).backgroundColor(Color.White).borderRadius(8)
            .onAppear(() => { if (index >= this.store.sessions.length - 6) this.store.loadMine(true); })
        }, (session: SessionSummary) => session.id)
        if (this.store.message) {
          Text(this.store.message).fontSize(12).fontColor('#65746F')
        }
        Button('退出登录').width('100%').type(ButtonType.Normal).fontColor('#C53D4B').onClick(() => this.store.logout())
      }.width('100%').padding(18)
    }.width('100%').height('100%').backgroundColor('#F3F6F4')
  }
}
