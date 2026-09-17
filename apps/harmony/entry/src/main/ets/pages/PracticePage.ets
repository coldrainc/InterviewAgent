import { EmptyState, PageHeader } from '../components/ProductComponents';
import { ProductStore } from '../state/ProductStore';

@Component
export struct PracticePage {
  @ObjectLink store: ProductStore;
  @State answer: string = '';

  build() {
    Scroll() {
      Column({ space: 14 }) {
        PageHeader('Practice', '刷题', '短时专注练习，及时复盘薄弱点')
        if (!this.store.questions.length) {
          EmptyState('题库暂时为空', '刷新题库后开始练习。')
          Button('刷新题库').onClick(() => this.store.loadPractice())
        } else {
          Text(`${this.store.questionIndex + 1} / ${this.store.questions.length}`).fontSize(12).fontColor('#65746F')
          Column({ space: 14 }) {
            Text(this.store.questions[this.store.questionIndex].prompt).fontSize(17).fontWeight(FontWeight.Medium)
            if (this.store.questions[this.store.questionIndex].choices.length) {
              ForEach(this.store.questions[this.store.questionIndex].choices, (choice: string, index: number) => {
                Button(`${String.fromCharCode(65 + index)}. ${choice}`).width('100%')
                  .type(this.answer === String.fromCharCode(65 + index) ? ButtonType.Capsule : ButtonType.Normal)
                  .onClick(() => this.answer = String.fromCharCode(65 + index))
              }, (choice: string, index: number) => `${index}-${choice}`)
            } else {
              TextArea({ placeholder: '写下你的答题思路', text: this.answer }).height(150).onChange((value: string) => this.answer = value)
            }
            Row({ space: 8 }) {
              Button('下一题').layoutWeight(1).onClick(() => { this.answer = ''; this.store.nextQuestion(); })
              Button('提交').layoutWeight(1).enabled(Boolean(this.answer.trim()) && !this.store.busy)
                .onClick(() => this.store.submitPractice(this.answer))
            }.width('100%')
          }.width('100%').padding(17).backgroundColor(Color.White).borderRadius(8)
          if (this.store.practiceResult) {
            Column({ space: 8 }) {
              Text(`${this.store.practiceResult?.score ?? 0} 分`).fontSize(28).fontWeight(FontWeight.Bold).fontColor('#27735F')
              Text(this.store.practiceResult?.feedback ?? '').fontSize(14)
              Text(this.store.practiceResult?.explanation ?? '').fontSize(13).fontColor('#65746F')
            }.alignItems(HorizontalAlign.Start).width('100%').padding(17).backgroundColor('#E2F3ED').borderRadius(8)
          }
        }
      }.width('100%').padding(18)
    }.width('100%').height('100%').backgroundColor('#F3F6F4')
  }
}
