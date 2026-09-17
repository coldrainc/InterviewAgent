import { AccountCenter } from "../components/account/AccountCenter";
import { AdminConsole } from "../components/admin/AdminConsole";
import { EmptyState, Message, Typing, Composer } from "../components/chat/Chat";
import { HomePage } from "../components/home/HomePage";
import { InterviewerWorkspacePage } from "../components/interview/InterviewerWorkspacePage";
import { ReportsPage } from "../components/interview/ReportsPage";
import { OperationsCenter } from "../components/operations/OperationsCenter";
import { SettingsCenter } from "../components/settings/SettingsCenter";
import { SetupCenter } from "../components/setup/SetupCenter";
import { PlanGeneratorPage } from "../components/study/PlanGeneratorPage";
import { ReviewSitePage } from "../components/study/ReviewSitePage";
import { TrainingPage } from "../components/training/TrainingPage";
import { currentIndustry } from "../utils/interview";

export function AppScreenRouter({ screen, model }) {
  const {
    account,
    admin,
    chat,
    home,
    interviewer,
    operations,
    planner,
    reports,
    review,
    settings,
    setup,
    training
  } = model;

  if (screen === "account") return <AccountCenter {...account} />;
  if (screen === "admin") return <AdminConsole {...admin} />;
  if (screen === "settings") return <SettingsCenter {...settings} />;
  if (screen === "ops") return <OperationsCenter {...operations} />;
  if (screen === "setup") return <SetupCenter {...setup} />;
  if (screen === "home") return <HomePage {...home} />;
  if (screen === "reports") return <ReportsPage {...reports} />;
  if (screen === "interviewer-workspace") return <InterviewerWorkspacePage {...interviewer} />;
  if (screen === "practice") return <TrainingPage {...training} />;
  if (screen === "review-site") return <ReviewSitePage {...review} />;
  if (screen === "planner") return <PlanGeneratorPage {...planner} />;

  return <ChatWorkspace {...chat} />;
}

function ChatWorkspace({
  busy,
  industryOptions,
  input,
  messages,
  messagesEndRef,
  onEditMessage,
  onInputChange,
  onKeyDown,
  onQuickPrompt,
  onStart,
  onStop,
  onSubmit,
  onWithdrawMessage,
  profile,
  sessionId,
  textareaRef
}) {
  return (
    <section className="chat-panel">
      <div className="messages">
        {messages.length === 0 ? (
          <EmptyState
            busy={busy}
            mode={profile.mode}
            industry={currentIndustry(industryOptions, profile.industry)}
            onStart={onStart}
            onQuickPrompt={onQuickPrompt}
          />
        ) : (
          messages.map((message) => (
            <Message
              key={message.id}
              message={message}
              mode={profile.mode}
              busy={busy}
              onEditMessage={onEditMessage}
              onWithdrawMessage={onWithdrawMessage}
            />
          ))
        )}
        {busy && <Typing />}
        <div ref={messagesEndRef} />
      </div>

      <Composer
        value={input}
        busy={busy}
        hasSession={Boolean(sessionId)}
        textareaRef={textareaRef}
        onChange={onInputChange}
        onSubmit={onSubmit}
        onKeyDown={onKeyDown}
        onStop={onStop}
        mode={profile.mode}
      />
    </section>
  );
}
