@Builder
export function PageHeader(eyebrow: string, title: string, subtitle: string) {
  Column({ space: 5 }) {
    Text(eyebrow.toUpperCase()).fontSize(11).fontColor('#27735F').fontWeight(FontWeight.Bold)
    Text(title).fontSize(28).fontWeight(FontWeight.Bold).fontColor('#15241F')
    Text(subtitle).fontSize(13).fontColor('#65746F')
  }
  .alignItems(HorizontalAlign.Start)
  .width('100%')
}

@Builder
export function SectionTitle(title: string, detail: string = '') {
  Row() {
    Text(title).fontSize(17).fontWeight(FontWeight.Bold).fontColor('#15241F')
    Blank()
    if (detail) {
      Text(detail).fontSize(12).fontColor('#65746F')
    }
  }
  .width('100%')
}

@Builder
export function EmptyState(title: string, detail: string) {
  Column({ space: 7 }) {
    Text(title).fontSize(16).fontWeight(FontWeight.Bold).fontColor('#15241F')
    Text(detail).fontSize(13).fontColor('#65746F').textAlign(TextAlign.Center)
  }
  .width('100%').padding(22).backgroundColor(Color.White).borderRadius(8)
}
