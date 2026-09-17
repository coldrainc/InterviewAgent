import common from '@ohos.app.ability.common';
import { AuthGate } from './AuthGate';
import { InterviewPage } from './InterviewPage';
import { MinePage } from './MinePage';
import { PracticePage } from './PracticePage';
import { ReviewPage } from './ReviewPage';
import { TodayPage } from './TodayPage';
import { AuthSession } from '../state/AuthSession';
import { ProductStore } from '../state/ProductStore';

@Entry
@Component
struct Index {
  @State store: ProductStore = new ProductStore();
  @State selectedTab: number = 0;

  aboutToAppear(): void {
    const context = getContext(this) as common.UIAbilityContext;
    AuthSession.initialize(context).then((token: string) => this.store.restore(token));
  }

  build() {
    if (!this.store.authenticated) {
      AuthGate({ store: this.store })
    } else {
      Tabs({ barPosition: BarPosition.End, index: this.selectedTab }) {
        TabContent() {
          TodayPage({
            store: this.store,
            onOpenTask: (task) => {
              this.store.openTask(task)
              this.selectedTab = task.task_type === 'interview' ? 1 : task.task_type === 'practice' ? 2 : 3
            }
          })
        }.tabBar('今日')
        TabContent() { InterviewPage({ store: this.store }) }.tabBar('面试')
        TabContent() { PracticePage({ store: this.store }) }.tabBar('刷题')
        TabContent() { ReviewPage({ store: this.store }) }.tabBar('复习')
        TabContent() { MinePage({ store: this.store }) }.tabBar('我的')
      }
      .barMode(BarMode.Fixed)
      .barBackgroundColor(Color.White)
      .onChange((index: number) => this.selectedTab = index)
    }
  }
}
