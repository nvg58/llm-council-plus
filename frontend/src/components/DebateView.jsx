import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import AdvisorGrid from './AdvisorGrid';
import './DebateView.css';

const toStr = (v) => (typeof v === 'string' ? v : String(v || ''));

function findPersona(personas, id) {
  return personas.find((p) => p.id === id) || null;
}

function RoundSection({ roundIndex, roundData, personas, isLast, isRunning }) {
  const responses = roundData.responses || [];

  return (
    <div className="debate-view__round">
      <div className="debate-view__round-header">
        <span className="debate-view__round-label">Round {roundIndex + 1}</span>
        <div className="debate-view__round-divider" />
      </div>

      <div className="debate-view__round-cards">
        {responses.map((resp, idx) => {
          const persona = findPersona(personas, resp.personaId);
          const hasError = !!resp.error;

          return (
            <div
              key={idx}
              className="debate-view__response-card"
              style={{ '--persona-color': persona?.color || '#64748b' }}
            >
              <div className="debate-view__response-header">
                <span className="debate-view__response-emoji">
                  {persona?.avatar_emoji || '🤖'}
                </span>
                <div className="debate-view__response-meta">
                  <span className="debate-view__response-name">
                    {persona?.name || resp.personaId}
                  </span>
                  <span className="debate-view__response-role">
                    {persona?.role || ''}
                  </span>
                </div>
                {hasError && (
                  <span className="debate-view__response-error-badge">Error</span>
                )}
              </div>
              <div className="debate-view__response-body">
                {hasError ? (
                  <div className="debate-view__response-error">
                    <span>⚠️</span>
                    <span>{resp.error_message || 'This advisor failed to respond.'}</span>
                  </div>
                ) : (
                  <div className="markdown-content">
                    <ReactMarkdown>{toStr(resp.content)}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Consensus / round transition banner */}
      {isLast && isRunning ? (
        <div className="debate-view__next-round-banner">
          <span className="debate-view__next-round-dot" />
          Next round starting...
        </div>
      ) : responses.length > 0 && !isRunning ? (
        <div className="debate-view__consensus-banner">
          {responses.every((r) => !r.error)
            ? '✅ All advisors completed this round'
            : '⚠️ Some advisors encountered errors'}
        </div>
      ) : null}
    </div>
  );
}

export default function DebateView({
  personas = [],
  rounds = [],
  verdict = null,
  tiebreaker = null,
  currentRound = 1,
  maxRounds = 3,
  isRunning = false,
  question = '',
  error = null,
}) {
  const [verdictCopied, setVerdictCopied] = useState(false);

  const activePersonaId = useMemo(() => {
    if (!isRunning) return null;
    const currentRoundData = rounds[currentRound - 1];
    if (!currentRoundData) return null;
    const responses = currentRoundData.responses || [];
    if (responses.length > 0) {
      const last = responses[responses.length - 1];
      if (!last.done) return last.personaId;
    }
    return null;
  }, [isRunning, rounds, currentRound]);

  const handleCopyVerdict = async () => {
    if (!verdict?.content) return;
    try {
      await navigator.clipboard.writeText(toStr(verdict.content));
      setVerdictCopied(true);
      setTimeout(() => setVerdictCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy verdict:', err);
    }
  };

  const hasResponses = rounds.some((r) => (r.responses || []).length > 0);
  const showDebateStarting = isRunning && !hasResponses;

  return (
    <div className="debate-view">
      {/* Advisor Grid — always shown at top */}
      <AdvisorGrid
        personas={personas}
        activePersonaId={activePersonaId}
        round={currentRound}
        maxRounds={maxRounds}
        isRunning={isRunning}
      />

      {/* Question echo */}
      {question && (
        <div className="debate-view__question">
          <span className="debate-view__question-label">Debating</span>
          <p className="debate-view__question-text">{question}</p>
        </div>
      )}

      {/* Live indicator — before any responses arrive */}
      {showDebateStarting && (
        <div className="debate-view__starting">
          <span className="debate-view__starting-spinner" aria-hidden="true" />
          Debate starting...
        </div>
      )}

      {/* Error banner — shown when the debate fails */}
      {error && (
        <div className="debate-view__error">
          <span className="debate-view__error-icon">⚠️</span>
          <div className="debate-view__error-content">
            <strong>Debate failed</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      {/* Round sections */}
      {rounds.map((roundData, idx) => {
        const hasContent = (roundData.responses || []).length > 0;
        if (!hasContent) return null;
        return (
          <RoundSection
            key={idx}
            roundIndex={idx}
            roundData={roundData}
            personas={personas}
            isLast={idx === rounds.length - 1}
            isRunning={isRunning}
          />
        );
      })}

      {/* Tiebreaker section */}
      {tiebreaker && tiebreaker.content && (
        <div className="debate-view__tiebreaker">
          <div className="debate-view__tiebreaker-header">
            <span className="debate-view__tiebreaker-icon">🔀</span>
            <span className="debate-view__tiebreaker-title">Tiebreaker</span>
            {tiebreaker.model && (
              <span className="debate-view__tiebreaker-model">{tiebreaker.model}</span>
            )}
          </div>
          <div className="markdown-content">
            <ReactMarkdown>{toStr(tiebreaker.content)}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Verdict section */}
      {verdict && verdict.content && (
        <div className={`debate-view__verdict ${verdict.error ? 'debate-view__verdict--error' : ''}`}>
          <div className="debate-view__verdict-header">
            <div className="debate-view__verdict-title-row">
              <span className="debate-view__verdict-icon">
                {verdict.error ? '⚠️' : '📋'}
              </span>
              <span className="debate-view__verdict-title">
                {verdict.error ? 'Verdict Error' : 'Verdict'}
              </span>
              {verdict.model && (
                <span className="debate-view__verdict-model">{verdict.model}</span>
              )}
            </div>
            {!verdict.error && (
              <button
                className={`debate-view__copy-btn ${verdictCopied ? 'debate-view__copy-btn--copied' : ''}`}
                onClick={handleCopyVerdict}
                type="button"
                title="Copy verdict to clipboard"
              >
                {verdictCopied ? (
                  <>
                    <span>✓</span>
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <span>📋</span>
                    <span>Copy</span>
                  </>
                )}
              </button>
            )}
          </div>
          <div className="debate-view__verdict-body markdown-content">
            <ReactMarkdown>{toStr(verdict.content)}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
