import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';

const STORE_NAME = 'interview_agent_auth';
const TOKEN_KEY = 'access_token';

export class AuthSession {
  private static store?: preferences.Preferences;

  static async initialize(context: common.Context): Promise<string> {
    AuthSession.store = await preferences.getPreferences(context, { name: STORE_NAME });
    return String(AuthSession.store.getSync(TOKEN_KEY, ''));
  }

  static async save(token: string): Promise<void> {
    if (!AuthSession.store) {
      return;
    }
    await AuthSession.store.put(TOKEN_KEY, token);
    await AuthSession.store.flush();
  }

  static async clear(): Promise<void> {
    if (!AuthSession.store) {
      return;
    }
    await AuthSession.store.delete(TOKEN_KEY);
    await AuthSession.store.flush();
  }
}
