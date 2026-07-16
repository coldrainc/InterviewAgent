import { currentModel, formatCredits } from "../../utils/interview";

export function ModelSelector({
  models,
  selectedModelId,
  onSelectModel,
  llmModes = [],
  selectedLlmMode = "",
  onSelectLlmMode
}) {
  const model = currentModel(models, selectedModelId);
  return (
    <div className="model-selector-stack">
      {llmModes.length > 0 && (
        <label className="select-field model-selector">
          <span>生成模式</span>
          <select value={selectedLlmMode} onChange={(event) => onSelectLlmMode?.(event.target.value)}>
            {llmModes.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
          <small>{llmModes.find((mode) => mode.value === selectedLlmMode)?.description}</small>
        </label>
      )}
      <label className="select-field model-selector">
        <span>模型</span>
        <select value={selectedModelId} onChange={(event) => onSelectModel(event.target.value)}>
          {models.map((item) => (
            <option key={item.id} value={item.id}>
              {item.category ? `${item.category} · ` : ""}
              {item.display_name || item.id}
            </option>
          ))}
        </select>
      {model && (
        <small>
          {model.category ? `${model.category} · ` : ""}
          {model.provider} · 输入 {formatCredits(model.input_credits_per_1m)} / 百万 token · 输出{" "}
          {formatCredits(model.output_credits_per_1m)} / 百万 token
        </small>
      )}
      </label>
    </div>
  );
}
