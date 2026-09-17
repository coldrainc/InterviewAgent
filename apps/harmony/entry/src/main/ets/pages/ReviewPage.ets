import { EmptyState, PageHeader, SectionTitle } from '../components/ProductComponents';
import { ReviewPlan } from '../model/Models';
import { ProductStore } from '../state/ProductStore';

@Component
export struct ReviewPage {
  @ObjectLink store: ProductStore;
  @State role: string = 'AI 应用工程师';
  @State focus: string = '项目深挖、系统设计、Agent 工程化';
  @State days: number = 14;
  @State note: string = '';

  build() {
    Scroll() {
      Column({ space: 14 }) {
        PageHeader('Review', '复习计划', '生成计划、按日执行、留下学习记录')
        if (this.store.activeTask && this.store.activeTask?.task_type !== 'practice' && this.store.activeTask?.task_type !== 'interview') {
          Column({ space: 5 }) {
            Text('当前任务').fontSize(12).fontColor('#27735F').fontWeight(FontWeight.Bold)
            Text(this.store.activeTask?.title ?? '').fontSize(16).fontWeight(FontWeight.Bold)
            Text('完成内容后可返回今日页更新状态。').fontSize(12).fontColor('#65746F')
          }.alignItems(HorizontalAlign.Start).width('100%').padding(16).backgroundColor(Color.White).borderRadius(8)
        }
        Column({ space: 10 }) {
          Text('生成专属计划').fontSize(17).fontWeight(FontWeight.Bold)
          TextInput({ placeholder: '目标岗位', text: this.role }).onChange((value: string) => this.role = value)
          TextInput({ placeholder: '重点方向，用顿号分隔', text: this.focus }).onChange((value: string) => this.focus = value)
          Row({ space: 10 }) {
            Text(`周期 ${this.days} 天`).fontSize(13).layoutWeight(1)
            Button('-').onClick(() => this.days = Math.max(3, this.days - 1))
            Button('+').onClick(() => this.days = Math.min(60, this.days + 1))
          }.width('100%')
          Button('生成复习计划').width('100%').enabled(!this.store.busy).onClick(() => this.store.generatePlan(this.role, this.days, this.focus))
        }.width('100%').padding(17).backgroundColor('#E9EEFF').borderRadius(8)
        SectionTitle('进行中的计划', `${this.store.plans.length} 个`)
        if (!this.store.plans.length) {
          EmptyState('还没有复习计划', '生成后可在这里选择计划并完成每日打卡。')
        }
        ForEach(this.store.plans, (plan: ReviewPlan, index: number) => {
          Row({ space: 10 }) {
            Column({ space: 4 }) {
              Text(plan.title).fontSize(15).fontWeight(FontWeight.Bold)
              Text(plan.subtitle ?? plan.status).fontSize(12).fontColor('#65746F')
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Radio({ value: plan.id, group: 'review-plan' }).checked(this.store.selectedPlanId === plan.id)
              .onChange((checked: boolean) => { if (checked) this.store.selectedPlanId = plan.id; })
          }.width('100%').padding(15).backgroundColor(Color.White).borderRadius(8)
            .onAppear(() => { if (index >= this.store.plans.length - 6) this.store.loadPlans(true); })
        }, (plan: ReviewPlan) => plan.id)
        if (this.store.selectedPlanId) {
          Column({ space: 9 }) {
            Text('今日打卡').fontSize(17).fontWeight(FontWeight.Bold)
            TextArea({ placeholder: '记录今天完成了什么', text: this.note }).height(90).onChange((value: string) => this.note = value)
            Button('完成 30 分钟打卡').width('100%').enabled(!this.store.busy).onClick(() => this.store.checkin(30, this.note))
          }.width('100%').padding(17).backgroundColor('#E2F3ED').borderRadius(8)
        }
      }.width('100%').padding(18)
    }.width('100%').height('100%').backgroundColor('#F3F6F4')
  }
}
