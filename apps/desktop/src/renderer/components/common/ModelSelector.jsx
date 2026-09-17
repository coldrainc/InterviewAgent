import { currentModel } from "../../utils/interview";

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
          不同模型消耗标准不同，完成后会展示本次积分明细
        </small>
      )}
      </label>
    </div>
  );
}
