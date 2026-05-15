import React, { useState, useEffect } from 'react';
import { api } from '../api';
import './AdvisorSetup.css';

const RECOMMENDED_PERSONA_IDS = ['skeptic', 'pragmatist', 'innovator'];

export default function AdvisorSetup({
  onStartDebate,
  isLoading = false,
}) {
  const [personas, setPersonas] = useState([]);
  const [personasLoading, setPersonasLoading] = useState(true);
  const [models, setModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState([]);
  const [modelMode, setModelMode] = useState('simple');
  const [chosenModel, setChosenModel] = useState('');
  const [modelAssignments, setModelAssignments] = useState({});
  const [rounds, setRounds] = useState(2);
  const [webSearch, setWebSearch] = useState(false);
  const [question, setQuestion] = useState('');

  // Fetch personas and all configured models on mount in parallel
  useEffect(() => {
    api.getPersonas()
      .then(setPersonas)
      .catch(() => setPersonas([]))
      .finally(() => setPersonasLoading(false));

    const fetchModels = async () => {
      try {
        const settings = await api.getSettings();
        const enabled = settings.enabled_providers || {};
        const ollamaUrl = settings.ollama_base_url || 'http://localhost:11434';

        const [orModels, ollamaModels, directModels, customModels] = await Promise.all([
          enabled.openrouter
            ? api.getModels().then(d => d.models || []).catch(() => [])
            : [],
          enabled.ollama
            ? api.getOllamaModels(ollamaUrl).then(d => (d.models || []).map(m => ({
                ...m,
                id: m.id.startsWith('ollama:') ? m.id : `ollama:${m.id}`,
                name: `${m.name || m.id} (Local)`,
                provider: 'Ollama',
              }))).catch(() => [])
            : [],
          (enabled.groq || enabled.direct)
            ? api.getDirectModels().then(d => Array.isArray(d) ? d : (d.models || [])).catch(() => [])
            : [],
          enabled.custom
            ? api.getCustomEndpointModels().then(d => d.models || []).catch(() => [])
            : [],
        ]);

        const combined = [...orModels, ...ollamaModels, ...directModels, ...customModels];
        const unique = new Map();
        combined.forEach(m => unique.set(m.id, m));
        const sorted = Array.from(unique.values())
          .sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        setModels(sorted);

        // Pre-select advisor default model from settings
        if (settings.advisor_default_model) {
          setChosenModel(settings.advisor_default_model);
        } else if (sorted.length > 0) {
          setChosenModel(sorted[0].id);
        }

        if (settings.advisor_default_rounds) {
          setRounds(settings.advisor_default_rounds);
        }
      } catch (err) {
        console.error('Failed to load advisor models:', err);
      } finally {
        setModelsLoading(false);
      }
    };

    fetchModels();
  }, []);

  // ── Helpers ──────────────────────────────────────────────────────────────

  const togglePersona = (id) => {
    setSelectedPersonaIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((x) => x !== id);
      }
      if (prev.length >= 4) return prev; // max 4
      return [...prev, id];
    });
  };

  const handleUseRecommended = () => {
    setSelectedPersonaIds(RECOMMENDED_PERSONA_IDS);
    if (!chosenModel && models.length > 0) {
      setChosenModel(models[0].id);
    }
  };

  const handleModelAssignment = (personaId, modelId) => {
    setModelAssignments((prev) => ({ ...prev, [personaId]: modelId }));
  };

  const handleRoundsStep = (delta) => {
    setRounds((prev) => Math.min(10, Math.max(1, prev + delta)));
  };

  const canStart =
    selectedPersonaIds.length >= 2 &&
    (modelMode === 'simple' ? !!chosenModel : selectedPersonaIds.every((id) => !!modelAssignments[id])) &&
    question.trim().length > 0;

  const handleSubmit = () => {
    if (!canStart || isLoading) return;
    const payload = {
      question: question.trim(),
      personaIds: selectedPersonaIds,
      defaultModel: chosenModel,
      modelAssignments: modelMode === 'advanced' ? modelAssignments : null,
      maxRounds: rounds,
      webSearch,
    };
    onStartDebate(payload);
  };

  // ── Render ───────────────────────────────────────────────────────────────

  const selectedCount = selectedPersonaIds.length;

  return (
    <div className="advisor-setup">
      {/* Use Recommended Button */}
      <div className="advisor-setup__recommended-row">
        <button
          className="advisor-setup__recommended-btn"
          onClick={handleUseRecommended}
          type="button"
        >
          <span className="advisor-setup__recommended-icon">⚡</span>
          Use Recommended Panel
          <span className="advisor-setup__recommended-hint">Skeptic · Pragmatist · Innovator</span>
        </button>
      </div>

      {/* Persona Gallery */}
      <div className="advisor-setup__section">
        <div className="advisor-setup__section-header">
          <span className="advisor-setup__section-label">Choose Advisors</span>
          <span className={`advisor-setup__count-badge ${selectedCount >= 2 ? 'advisor-setup__count-badge--valid' : ''}`}>
            {selectedCount} / 4 selected
          </span>
        </div>

        {personasLoading ? (
          <div className="advisor-setup__personas-loading">Loading advisors...</div>
        ) : (
          <div className="advisor-setup__persona-gallery">
            {personas.map((persona) => {
              const selected = selectedPersonaIds.includes(persona.id);
              return (
                <button
                  key={persona.id}
                  type="button"
                  className={`advisor-setup__persona-card ${selected ? 'advisor-setup__persona-card--selected' : ''} ${!selected && selectedCount >= 4 ? 'advisor-setup__persona-card--disabled' : ''}`}
                  onClick={() => togglePersona(persona.id)}
                  style={selected ? { '--persona-color': persona.color } : {}}
                  aria-pressed={selected}
                >
                  <span className="advisor-setup__persona-emoji">{persona.avatar_emoji}</span>
                  <span className="advisor-setup__persona-name">{persona.name}</span>
                  <span className="advisor-setup__persona-role">{persona.role}</span>
                  <span className="advisor-setup__persona-desc">{persona.description}</span>
                  {selected && (
                    <span className="advisor-setup__persona-check" style={{ backgroundColor: persona.color }}>
                      ✓
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Model Assignment */}
      <div className="advisor-setup__section">
        <div className="advisor-setup__section-header">
          <span className="advisor-setup__section-label">Model Assignment</span>
          <div className="advisor-setup__mode-tabs">
            <button
              type="button"
              className={`advisor-setup__mode-tab ${modelMode === 'simple' ? 'advisor-setup__mode-tab--active' : ''}`}
              onClick={() => setModelMode('simple')}
            >
              Simple
            </button>
            <button
              type="button"
              className={`advisor-setup__mode-tab ${modelMode === 'advanced' ? 'advisor-setup__mode-tab--active' : ''}`}
              onClick={() => setModelMode('advanced')}
            >
              Advanced
            </button>
          </div>
        </div>

        {modelMode === 'simple' ? (
          <div className="advisor-setup__model-simple">
            <label className="advisor-setup__model-label" htmlFor="advisor-model-select">
              All advisors use the same model
            </label>
            <select
              id="advisor-model-select"
              className="advisor-setup__model-select"
              value={chosenModel}
              onChange={(e) => setChosenModel(e.target.value)}
              disabled={modelsLoading}
            >
              <option value="">{modelsLoading ? 'Loading models…' : `Select a model (${models.length} available)…`}</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="advisor-setup__model-advanced">
            {selectedPersonaIds.length === 0 ? (
              <p className="advisor-setup__model-advanced-empty">
                Select at least one advisor above to assign models.
              </p>
            ) : (
              selectedPersonaIds.map((id) => {
                const persona = personas.find((p) => p.id === id);
                if (!persona) return null;
                return (
                  <div key={id} className="advisor-setup__model-row">
                    <span className="advisor-setup__model-row-persona">
                      <span>{persona.avatar_emoji}</span>
                      <span>{persona.name}</span>
                    </span>
                    <select
                      className="advisor-setup__model-select"
                      value={modelAssignments[id] || ''}
                      onChange={(e) => handleModelAssignment(id, e.target.value)}
                      disabled={modelsLoading}
                    >
                      <option value="">{modelsLoading ? 'Loading…' : 'Select a model…'}</option>
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Debate Config Row */}
      <div className="advisor-setup__section">
        <div className="advisor-setup__config-row">
          <div className="advisor-setup__rounds">
            <span className="advisor-setup__config-label">Rounds</span>
            <div className="advisor-setup__stepper">
              <button
                type="button"
                className="advisor-setup__stepper-btn"
                onClick={() => handleRoundsStep(-1)}
                disabled={rounds <= 1}
                aria-label="Decrease rounds"
              >
                −
              </button>
              <span className="advisor-setup__stepper-value">{rounds}</span>
              <button
                type="button"
                className="advisor-setup__stepper-btn"
                onClick={() => handleRoundsStep(1)}
                disabled={rounds >= 10}
                aria-label="Increase rounds"
              >
                +
              </button>
            </div>
          </div>

          <label className="advisor-setup__websearch-toggle">
            <span className="advisor-setup__config-label">
              <span aria-hidden="true">🌐</span> Web Search
            </span>
            <div
              className={`advisor-setup__toggle ${webSearch ? 'advisor-setup__toggle--on' : ''}`}
              onClick={() => setWebSearch((prev) => !prev)}
              role="switch"
              aria-checked={webSearch}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === ' ' || e.key === 'Enter') setWebSearch((prev) => !prev);
              }}
            >
              <div className="advisor-setup__toggle-knob" />
            </div>
          </label>
        </div>
      </div>

      {/* Question Textarea */}
      <div className="advisor-setup__section">
        <label className="advisor-setup__section-label" htmlFor="advisor-question">
          Debate Question
        </label>
        <textarea
          id="advisor-question"
          className="advisor-setup__question"
          placeholder="What should your advisors debate?"
          rows={4}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
      </div>

      {/* Start Button */}
      <button
        type="button"
        className={`advisor-setup__start-btn ${canStart && !isLoading ? 'advisor-setup__start-btn--ready' : ''}`}
        onClick={handleSubmit}
        disabled={!canStart || isLoading}
      >
        {isLoading ? (
          <>
            <span className="advisor-setup__spinner" aria-hidden="true" />
            Starting Debate...
          </>
        ) : (
          'Start Debate'
        )}
      </button>

      {/* Validation hint */}
      {!canStart && !isLoading && (
        <p className="advisor-setup__hint">
          {selectedPersonaIds.length < 2
            ? 'Select at least 2 advisors'
            : modelMode === 'simple' && !chosenModel
              ? 'Choose a model'
              : modelMode === 'advanced' && !selectedPersonaIds.every((id) => !!modelAssignments[id])
                ? 'Assign a model to each selected advisor'
                : 'Enter a debate question'}
        </p>
      )}
    </div>
  );
}
