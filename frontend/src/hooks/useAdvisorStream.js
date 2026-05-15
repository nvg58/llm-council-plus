import { useState, useRef, useCallback } from 'react';
import { api } from '../api';

const initialDebateState = {
  isRunning: false,
  currentRound: 0,
  maxRounds: 0,
  personas: [],
  rounds: [],
  verdict: null,
  tiebreaker: null,
  consensusReached: false,
  error: null,
};

export function useAdvisorStream() {
  const [debateState, setDebateState] = useState(initialDebateState);
  const abortControllerRef = useRef(null);

  const startDebate = useCallback(async (conversationId, options, onEvent) => {
    abortControllerRef.current = new AbortController();

    setDebateState({
      ...initialDebateState,
      isRunning: true,
    });

    try {
      await api.sendDebateStream(
        conversationId,
        options,
        (eventType, event) => {
          switch (eventType) {
            case 'advisor_debate_start':
              setDebateState((prev) => ({
                ...prev,
                personas: event.personas || [],
                maxRounds: event.max_rounds || 0,
              }));
              break;

            case 'advisor_round_start':
              setDebateState((prev) => ({
                ...prev,
                currentRound: event.round || prev.currentRound,
              }));
              break;

            case 'advisor_response':
              setDebateState((prev) => {
                const rounds = [...prev.rounds];
                const roundIndex = (event.round || 1) - 1;
                if (!rounds[roundIndex]) {
                  rounds[roundIndex] = { round: event.round, responses: [], complete: false, consensusReached: false };
                }
                rounds[roundIndex] = {
                  ...rounds[roundIndex],
                  responses: [...rounds[roundIndex].responses, event.data],
                };
                return { ...prev, rounds };
              });
              break;

            case 'advisor_round_complete':
              setDebateState((prev) => {
                const rounds = [...prev.rounds];
                const roundIndex = (event.round || 1) - 1;
                if (!rounds[roundIndex]) {
                  rounds[roundIndex] = { round: event.round, responses: [], complete: false, consensusReached: false };
                }
                rounds[roundIndex] = {
                  ...rounds[roundIndex],
                  complete: true,
                  consensusReached: event.consensus_reached || false,
                };
                return { ...prev, rounds, consensusReached: event.consensus_reached || false };
              });
              break;

            case 'advisor_verdict':
              setDebateState((prev) => ({
                ...prev,
                verdict: event.data || event,
              }));
              break;

            case 'advisor_tiebreaker':
              setDebateState((prev) => ({
                ...prev,
                tiebreaker: event.data || event,
              }));
              break;

            case 'advisor_complete':
              setDebateState((prev) => ({
                ...prev,
                isRunning: false,
              }));
              break;

            case 'advisor_error':
              setDebateState((prev) => ({
                ...prev,
                isRunning: false,
                error: event.message || 'Advisor debate failed',
              }));
              break;

            default:
              break;
          }

          if (onEvent) {
            onEvent(eventType, event);
          }
        },
        abortControllerRef.current.signal
      );
    } catch (error) {
      if (error.name === 'AbortError') {
        setDebateState((prev) => ({
          ...prev,
          isRunning: false,
        }));
        return;
      }
      setDebateState((prev) => ({
        ...prev,
        isRunning: false,
        error: error.message || 'Debate stream failed',
      }));
    } finally {
      abortControllerRef.current = null;
    }
  }, []);

  const stopDebate = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  return { debateState, startDebate, stopDebate };
}
