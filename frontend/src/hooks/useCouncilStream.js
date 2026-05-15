import { useState, useRef, useCallback } from 'react';
import { api } from '../api';

export function useCouncilStream() {
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef(null);
  const requestIdRef = useRef(0);

  const sendMessage = useCallback(async (conversationId, options, onStateUpdate, onConversationsReload) => {
    const { content, webSearch, executionMode } = options;

    const currentRequestId = ++requestIdRef.current;
    abortControllerRef.current = new AbortController();
    setIsLoading(true);

    const userMessage = { role: 'user', content };
    onStateUpdate((prev) => ({
      ...prev,
      messages: [...prev.messages, userMessage],
    }));

    const assistantMessage = {
      role: 'assistant',
      stage1: null,
      stage2: null,
      stage3: null,
      metadata: null,
      loading: {
        search: false,
        stage1: false,
        stage2: false,
        stage3: false,
      },
      timers: {
        stage1Start: null,
        stage1End: null,
        stage2Start: null,
        stage2End: null,
        stage3Start: null,
        stage3End: null,
      },
      progress: {
        stage1: { count: 0, total: 0, currentModel: null },
        stage2: { count: 0, total: 0, currentModel: null },
      },
    };

    onStateUpdate((prev) => ({
      ...prev,
      messages: [...prev.messages, assistantMessage],
    }));

    try {
      await api.sendMessageStream(
        conversationId,
        { content, webSearch, executionMode },
        (eventType, event) => {
          switch (eventType) {
            case 'search_start':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  loading: { ...lastMsg.loading, search: true },
                };
                return { ...prev, messages };
              });
              break;

            case 'search_complete':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  loading: { ...lastMsg.loading, search: false },
                  metadata: {
                    ...lastMsg.metadata,
                    search_query: event.data.search_query,
                    extracted_query: event.data.extracted_query,
                    search_context: event.data.search_context,
                  },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage1_start':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  loading: { ...lastMsg.loading, stage1: true },
                  timers: { ...lastMsg.timers, stage1Start: Date.now() },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage1_init':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  progress: {
                    ...lastMsg.progress,
                    stage1: { count: 0, total: event.total, currentModel: null },
                  },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage1_progress':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                const updatedStage1 = lastMsg.stage1 ? [...lastMsg.stage1, event.data] : [event.data];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  progress: {
                    ...lastMsg.progress,
                    stage1: { count: event.count, total: event.total, currentModel: event.data.model },
                  },
                  stage1: updatedStage1,
                };
                return { ...prev, messages };
              });
              break;

            case 'stage1_complete':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  stage1: event.data,
                  loading: { ...lastMsg.loading, stage1: false },
                  timers: { ...lastMsg.timers, stage1End: Date.now() },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage2_start':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  loading: { ...lastMsg.loading, stage2: true },
                  timers: { ...lastMsg.timers, stage2Start: Date.now() },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage2_init':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  progress: {
                    ...lastMsg.progress,
                    stage2: { count: 0, total: event.total, currentModel: null },
                  },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage2_progress':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                const updatedStage2 = lastMsg.stage2 ? [...lastMsg.stage2, event.data] : [event.data];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  progress: {
                    ...lastMsg.progress,
                    stage2: { count: event.count, total: event.total, currentModel: event.data.model },
                  },
                  stage2: updatedStage2,
                };
                return { ...prev, messages };
              });
              break;

            case 'stage2_complete':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  stage2: event.data,
                  loading: { ...lastMsg.loading, stage2: false },
                  timers: { ...lastMsg.timers, stage2End: Date.now() },
                  metadata: { ...lastMsg.metadata, ...event.metadata },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage3_start':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  loading: { ...lastMsg.loading, stage3: true },
                  timers: { ...lastMsg.timers, stage3Start: Date.now() },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage3_complete':
              onStateUpdate((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMsg,
                  stage3: event.data,
                  loading: { ...lastMsg.loading, stage3: false },
                  timers: { ...lastMsg.timers, stage3End: Date.now() },
                };
                return { ...prev, messages };
              });
              setIsLoading(false);
              break;

            case 'title_complete':
              if (onConversationsReload) onConversationsReload();
              break;

            case 'complete':
              if (onConversationsReload) onConversationsReload();
              setIsLoading(false);
              break;

            case 'error':
              console.error('Stream error:', event.message);
              setIsLoading(false);
              break;

            default:
              break;
          }
        },
        abortControllerRef.current.signal
      );
    } catch (error) {
      if (error.name === 'AbortError') {
        onStateUpdate((prev) => {
          if (!prev || prev.messages.length < 2) return prev;
          const messages = [...prev.messages];
          const lastMsg = messages[messages.length - 1];
          if (lastMsg.role === 'assistant') {
            const now = Date.now();
            messages[messages.length - 1] = {
              ...lastMsg,
              aborted: true,
              loading: { search: false, stage1: false, stage2: false, stage3: false },
              timers: {
                ...lastMsg.timers,
                stage1End: lastMsg.timers?.stage1Start && !lastMsg.timers?.stage1End ? now : lastMsg.timers?.stage1End,
                stage2End: lastMsg.timers?.stage2Start && !lastMsg.timers?.stage2End ? now : lastMsg.timers?.stage2End,
                stage3End: lastMsg.timers?.stage3Start && !lastMsg.timers?.stage3End ? now : lastMsg.timers?.stage3End,
              },
            };
          }
          return { ...prev, messages };
        });
        return;
      }
      console.error('Failed to send message:', error);
      onStateUpdate((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    } finally {
      if (requestIdRef.current === currentRequestId) {
        abortControllerRef.current = null;
      }
      if (onConversationsReload) onConversationsReload();
    }
  }, []);

  const abortMessage = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
    }
  }, []);

  return { sendMessage, isLoading, abortMessage };
}
