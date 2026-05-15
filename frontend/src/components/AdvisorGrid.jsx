import React from 'react';
import './AdvisorGrid.css';

export default function AdvisorGrid({
  personas = [],
  activePersonaId = null,
  round = 1,
  maxRounds = 3,
  isRunning = false,
}) {
  if (!personas || personas.length === 0) return null;

  return (
    <div className="advisor-grid-wrapper">
      <div className="advisor-round-indicator">
        Round {round} of {maxRounds}
      </div>
      <div className="advisor-grid">
        {personas.map((persona) => {
          const isActive = persona.id === activePersonaId;

          // thinking = currently speaking
          // done = debate finished (not running, no active persona)
          // waiting = debate running but not this persona's turn
          // idle = before debate starts
          let cardState = 'idle';
          if (isActive) {
            cardState = 'thinking';
          } else if (isRunning) {
            cardState = 'waiting';
          } else if (!isRunning && activePersonaId === null) {
            cardState = 'idle';
          }

          return (
            <div
              key={persona.id}
              className={`advisor-card advisor-card--${cardState}`}
              style={{ '--persona-color': persona.color }}
            >
              <div className="advisor-avatar-wrap">
                <div
                  className="advisor-avatar"
                  style={{ backgroundColor: persona.color + '26' }}
                >
                  <span className="advisor-emoji">{persona.avatar_emoji}</span>
                  {cardState === 'thinking' && (
                    <div
                      className="advisor-thinking-ring"
                      style={{ borderColor: persona.color }}
                    />
                  )}
                  {/* Show done badge only after debate has run (not running, and at least one round existed) */}
                  {!isRunning && !isActive && round > 1 && (
                    <div className="advisor-done-badge">✓</div>
                  )}
                </div>
              </div>
              <div className="advisor-info">
                <span className="advisor-name">{persona.name}</span>
                <span className="advisor-role">{persona.role}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
