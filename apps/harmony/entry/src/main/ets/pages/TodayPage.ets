import { EmptyState, PageHeader, SectionTitle } from '../components/ProductComponents';
import { LearningTask } from '../model/Models';
import { ProductStore } from '../state/ProductStore';

@Component
export struct TodayPage {
  @ObjectLink store: ProductStore;
  onOpenTask: (task: LearningTask) => void = () => {};

  build() {
    Scroll() {
      Column({ space: 16 }) {
        PageHeader('Today', '今日', '把注意力放在最重要的下一步')
        Column({ space: 8 }) {
          Text('下一最佳行动').fontSize(12).fontColor('#27735F').fontWeight(FontWeight.Bold)
          Text(this.store.today?.next_best_action?.title ?? '完成一次轻量模拟面试').fontSize(21).fontWeight(FontWeight.Bold).fontColor('#15241F')
          Text(this.store.today?.next_best_action?.reason ?? '保持表达与思考手感').fontSize(13).fontColor('#65746F')
        }.width('100%').padding(18).backgroundColor('#E2F3ED').borderRadius(8)
        SectionTitle('今日任务', `${this.store.today?.today?.tasks_done ?? 0} / ${this.store.today?.today?.total_tasks ?? 0}`)
        if ((this.store.today?.today?.tasks.length ?? 0) === 0) {
          EmptyState('今天还没有任务', '生成复习计划后，任务会自动出现在这里。')
        } else {
          ForEach(this.store.today?.today?.tasks ?? [], (task: LearningTask, index: number) => {
            Row({ space: 12 }) {
              Text(task.done ? '✓' : `${index + 1}`).fontSize(15).fontColor(task.done ? '#27735F' : '#315BE8')
                .width(30).height(30).textAlign(TextAlign.Center).backgroundColor(task.done ? '#E2F3ED' : '#E9EEFF').borderRadius(15)
              Column({ space: 4 }) {
                Text(task.title).fontSize(15).fontWeight(FontWeight.Medium).fontColor('#15241F')
                Text(task.task_type).fontSize(11).fontColor('#65746F')
              }.layoutWeight(1).alignItems(HorizontalAlign.Start).onClick(() => this.onOpenTask(task))
              Button(task.primary_action?.label ?? (task.done ? '重做' : '开始')).fontSize(12).enabled(!this.store.busy)
                .onClick(() => this.store.runTask(task))
            }.width('100%').padding(15).backgroundColor(Color.White).borderRadius(8)
          }, (task: LearningTask) => task.id)
        }
      }.width('100%').padding(18)
    }.width('100%').height('100%').backgroundColor('#F3F6F4')
  }
}
