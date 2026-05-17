import React, { useState, useEffect, useRef } from 'react';
import { api, buildAvailableSearchProviders } from '../api';
import SearchableModelSelect from './SearchableModelSelect';
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
  const [editingPersona, setEditingPersona] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', role: '', description: '', system_prompt: '', avatar_emoji: '' });
  const [editSaving, setEditSaving] = useState(false);
  const [searchProvider, setSearchProvider] = useState(null);
  const [availableSearchProviders, setAvailableSearchProviders] = useState([{ id: 'duckduckgo', name: 'DuckDuckGo' }]);
  const [searchPopoverOpen, setSearchPopoverOpen] = useState(false);
  const searchPopoverRef = useRef(null);
  const [question, setQuestion] = useState('');
  const [personasExpanded, setPersonasExpanded] = useState(true);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchPopoverRef.current && !searchPopoverRef.current.contains(e.target)) {
        setSearchPopoverOpen(false);
      }
    };
    if (searchPopoverOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [searchPopoverOpen]);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const [personasResult, settings] = await Promise.all([
          api.getPersonas().catch(() => []),
          api.getSettings(),
        ]);
        setPersonas(personasResult);

        setAvailableSearchProviders(buildAvailableSearchProviders(settings));

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
        setPersonasLoading(false);
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

  const openEditModal = (e, persona) => {
    e.stopPropagation();
    setEditingPersona(persona);
    setEditForm({
      name: persona.name,
      role: persona.role,
      description: persona.description,
      system_prompt: persona.system_prompt,
      avatar_emoji: persona.avatar_emoji,
    });
  };

  const closeEditModal = () => {
    setEditingPersona(null);
    setEditSaving(false);
  };

  const runEditAction = async (apiFn, errorMsg) => {
    if (!editingPersona || editSaving) return;
    setEditSaving(true);
    try {
      const result = await apiFn(editingPersona.id);
      setPersonas((prev) => prev.map((p) => p.id === result.id ? result : p));
      closeEditModal();
    } catch (err) {
      console.error(errorMsg, err);
      setEditSaving(false);
    }
  };

  const handleEditSave = () => runEditAction(
    (id) => api.updatePersona(id, editForm),
    'Failed to save persona:'
  );

  const handleEditReset = () => runEditAction(
    api.resetPersona,
    'Failed to reset persona:'
  );

  const canStart =
    selectedPersonaIds.length >= 2 &&
    (modelMode === 'simple' ? !!chosenModel : selectedPersonaIds.every((id) => !!modelAssignments[id])) &&
    question.trim().length > 0;

  const getHint = () => {
    if (canStart) return '↵ Enter to start · Shift+Enter for new line';
    if (question.trim().length === 0) return 'Fill in the form below, then start your debate';
    if (selectedPersonaIds.length < 2) return '⚠ Select at least 2 advisors below';
    if (modelMode === 'simple' && !chosenModel) return '⚠ Choose a model below';
    return '⚠ Assign a model to each advisor';
  };

  const handleSubmit = () => {
    if (!canStart || isLoading) return;
    const payload = {
      question: question.trim(),
      personaIds: selectedPersonaIds,
      defaultModel: chosenModel,
      modelAssignments: modelMode === 'advanced' ? modelAssignments : null,
      maxRounds: rounds,
      searchProvider,
    };
    onStartDebate(payload);
  };

  // ── Render ───────────────────────────────────────────────────────────────

  const selectedCount = selectedPersonaIds.length;

  return (
    <div className="advisor-setup">
      {/* Question Textarea + Start Debate — primary input card */}
      <div className="advisor-setup__section advisor-setup__question-card">
        <label className="advisor-setup__section-label" htmlFor="advisor-question">
          Debate Question
        </label>
        <textarea
          id="advisor-question"
          className="advisor-setup__question"
          placeholder="What should your advisors debate? (Shift+Enter for new line)"
          rows={4}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <div className="advisor-setup__question-footer">
          <span className="advisor-setup__question-hint">
            {getHint()}
          </span>
          <button
            type="button"
            className={`advisor-setup__start-btn advisor-setup__start-btn--inline ${canStart && !isLoading ? 'advisor-setup__start-btn--ready' : ''}`}
            onClick={handleSubmit}
            disabled={!canStart || isLoading}
          >
            {isLoading ? (
              <><span className="advisor-setup__spinner" aria-hidden="true" /> Starting…</>
            ) : (
              'Start Debate ➤'
            )}
          </button>
        </div>
      </div>

      {/* Rounds + Web Search — compact config directly below question */}
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

          <div className="advisor-setup__websearch-picker" ref={searchPopoverRef}>
            <span className="advisor-setup__config-label">Web Search</span>
            <button
              type="button"
              className={`advisor-setup__search-btn ${searchProvider ? 'advisor-setup__search-btn--active' : ''}`}
              onClick={() => setSearchPopoverOpen((v) => !v)}
              aria-haspopup="listbox"
              aria-expanded={searchPopoverOpen}
            >
              <span>🌐</span>
              <span>{searchProvider ? (availableSearchProviders.find(p => p.id === searchProvider)?.name || searchProvider) : 'Off'}</span>
              <span className="advisor-setup__search-chevron">›</span>
            </button>
            {searchPopoverOpen && (
              <div className="advisor-setup__search-popover" role="listbox">
                <button
                  type="button"
                  className={`advisor-setup__search-option ${!searchProvider ? 'advisor-setup__search-option--selected' : ''}`}
                  onClick={() => { setSearchProvider(null); setSearchPopoverOpen(false); }}
                >
                  <span>✕</span> Off
                </button>
                {availableSearchProviders.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`advisor-setup__search-option ${searchProvider === p.id ? 'advisor-setup__search-option--selected' : ''}`}
                    onClick={() => { setSearchProvider(p.id); setSearchPopoverOpen(false); }}
                  >
                    <span>🌐</span> {p.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Persona Gallery */}
      <div className="advisor-setup__section">
        <button
          type="button"
          className="advisor-setup__section-header advisor-setup__section-header--collapsible"
          onClick={() => setPersonasExpanded((v) => !v)}
          aria-expanded={personasExpanded}
        >
          <span className="advisor-setup__section-label">Choose Advisors</span>
          <div className="advisor-setup__section-header-right">
            <span className={`advisor-setup__count-badge ${selectedCount >= 2 ? 'advisor-setup__count-badge--valid' : ''}`}>
              {selectedCount} / 4 selected
            </span>
            <span className={`advisor-setup__chevron ${personasExpanded ? '' : 'advisor-setup__chevron--collapsed'}`}>
              ›
            </span>
          </div>
        </button>

        <div className={`advisor-setup__collapsible ${personasExpanded ? 'advisor-setup__collapsible--open' : ''}`}>
          <div className="advisor-setup__collapsible-inner">
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

            {personasLoading ? (
              <div className="advisor-setup__personas-loading">Loading advisors...</div>
            ) : (
              <div className="advisor-setup__persona-gallery">
                {personas.map((persona) => {
                  const selected = selectedPersonaIds.includes(persona.id);
                  return (
                    <div
                      key={persona.id}
                      role="button"
                      tabIndex={!selected && selectedCount >= 4 ? -1 : 0}
                      className={`advisor-setup__persona-card ${selected ? 'advisor-setup__persona-card--selected' : ''} ${!selected && selectedCount >= 4 ? 'advisor-setup__persona-card--disabled' : ''} ${persona.is_customized ? 'advisor-setup__persona-card--customized' : ''}`}
                      onClick={() => togglePersona(persona.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); togglePersona(persona.id); } }}
                      style={selected ? { '--persona-color': persona.color } : {}}
                      aria-pressed={selected}
                    >
                      <button
                        type="button"
                        className="advisor-setup__persona-edit-btn"
                        onClick={(e) => openEditModal(e, persona)}
                        title="Edit persona"
                        aria-label={`Edit ${persona.name}`}
                        tabIndex={0}
                      >
                        ✏️
                      </button>
                      <span className="advisor-setup__persona-emoji">{persona.avatar_emoji}</span>
                      <span className="advisor-setup__persona-name">{persona.name}</span>
                      <span className="advisor-setup__persona-role">{persona.role}</span>
                      <span className="advisor-setup__persona-desc">{persona.description}</span>
                      {persona.is_customized && (
                        <span className="advisor-setup__persona-custom-badge" title="Customized">✦</span>
                      )}
                      {selected && (
                        <span className="advisor-setup__persona-check" style={{ backgroundColor: persona.color }}>
                          ✓
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
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
            <label className="advisor-setup__model-label">
              All advisors use the same model
            </label>
            <SearchableModelSelect
              models={models}
              value={chosenModel}
              onChange={(id) => setChosenModel(id)}
              placeholder={modelsLoading ? 'Loading models…' : `Search ${models.length} models…`}
              isLoading={modelsLoading}
              isDisabled={modelsLoading}
            />
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
                    <SearchableModelSelect
                      models={models}
                      value={modelAssignments[id] || ''}
                      onChange={(modelId) => handleModelAssignment(id, modelId)}
                      placeholder={modelsLoading ? 'Loading…' : 'Search models…'}
                      isLoading={modelsLoading}
                      isDisabled={modelsLoading}
                    />
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Edit Persona Modal */}
      {editingPersona && (
        <div className="advisor-setup__edit-overlay" onClick={closeEditModal}>
          <div className="advisor-setup__edit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="advisor-setup__edit-header">
              <span className="advisor-setup__edit-emoji">{editingPersona.avatar_emoji}</span>
              <span className="advisor-setup__edit-title">Edit Persona</span>
              <button type="button" className="advisor-setup__edit-close" onClick={closeEditModal} aria-label="Close">✕</button>
            </div>

            <div className="advisor-setup__edit-body">
              <div className="advisor-setup__edit-emoji-row">
                <label className="advisor-setup__edit-field advisor-setup__edit-field--emoji">
                  <span className="advisor-setup__edit-label">Emoji / Icon</span>
                  <input
                    type="text"
                    className="advisor-setup__edit-input advisor-setup__edit-emoji-input"
                    value={editForm.avatar_emoji}
                    onChange={(e) => setEditForm((f) => ({ ...f, avatar_emoji: e.target.value }))}
                    placeholder="e.g. 🔍"
                    maxLength={4}
                  />
                </label>
                <div className="advisor-setup__edit-emoji-preview">
                  {editForm.avatar_emoji || editingPersona?.avatar_emoji}
                </div>
              </div>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">Name</span>
                <input
                  type="text"
                  className="advisor-setup__edit-input"
                  value={editForm.name}
                  onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                />
              </label>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">Role</span>
                <input
                  type="text"
                  className="advisor-setup__edit-input"
                  value={editForm.role}
                  onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value }))}
                />
              </label>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">Description</span>
                <textarea
                  className="advisor-setup__edit-textarea advisor-setup__edit-textarea--short"
                  rows={2}
                  value={editForm.description}
                  onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                />
              </label>

              <label className="advisor-setup__edit-field">
                <span className="advisor-setup__edit-label">System Prompt</span>
                <textarea
                  className="advisor-setup__edit-textarea"
                  rows={7}
                  value={editForm.system_prompt}
                  onChange={(e) => setEditForm((f) => ({ ...f, system_prompt: e.target.value }))}
                />
              </label>
            </div>

            <div className="advisor-setup__edit-footer">
              {editingPersona.is_customized && (
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--reset"
                  onClick={handleEditReset}
                  disabled={editSaving}
                >
                  Reset to Default
                </button>
              )}
              <div className="advisor-setup__edit-footer-right">
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--cancel"
                  onClick={closeEditModal}
                  disabled={editSaving}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="advisor-setup__edit-btn advisor-setup__edit-btn--save"
                  onClick={handleEditSave}
                  disabled={editSaving}
                >
                  {editSaving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
