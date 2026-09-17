import { ProductStore } from '../state/ProductStore';

@Component
export struct AuthGate {
  @ObjectLink store: ProductStore;
  @State email: string = '';
  @State password: string = '';
  @State displayName: string = '';
  @State registerMode: boolean = false;

  build() {
    Column({ space: 20 }) {
      Blank()
      Image($r('app.media.app_icon')).width(64).height(64).borderRadius(16)
      Column({ space: 6 }) {
        Text('Interview Agent').fontSize(30).fontWeight(FontWeight.Bold).fontColor('#15241F')
        Text('把每一次练习，变成下一次面试的底气').fontSize(14).fontColor('#65746F')
      }
      Column({ space: 12 }) {
        Text(this.registerMode ? '创建账号' : '欢迎回来').fontSize(20).fontWeight(FontWeight.Bold)
        if (this.registerMode) {
          TextInput({ placeholder: '你的称呼', text: this.displayName }).onChange((value: string) => this.displayName = value)
        }
        TextInput({ placeholder: '邮箱', text: this.email }).type(InputType.Email).onChange((value: string) => this.email = value)
        TextInput({ placeholder: '密码', text: this.password }).type(InputType.Password).onChange((value: string) => this.password = value)
        Button(this.registerMode ? '注册并开始' : '登录').width('100%')
          .enabled(!this.store.busy && Boolean(this.email.trim()) && this.password.length >= 8)
          .onClick(() => this.store.authenticate(this.email, this.password, this.displayName, this.registerMode))
        Button(this.registerMode ? '已有账号，去登录' : '没有账号，立即注册').width('100%').type(ButtonType.Normal)
          .onClick(() => this.registerMode = !this.registerMode)
        if (this.store.message) {
          Text(this.store.message).fontSize(12).fontColor('#C53D4B')
        }
      }.width('100%').padding(20).backgroundColor(Color.White).borderRadius(8)
      Text('你的简历、面试记录与学习计划仅对当前账号可见。').fontSize(12).fontColor('#65746F').textAlign(TextAlign.Center)
      Blank()
    }.width('100%').height('100%').padding(24).backgroundColor('#F3F6F4')
  }
}
