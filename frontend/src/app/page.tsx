"use client";

import { useState, useRef, useEffect, useCallback } from "react";

// ==========================================
//  Types
// ==========================================

interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
  city: string;
  total_spent: number;
  order_count: number;
  last_order_date: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  customers?: Customer[];
  segmentSize?: number;
  segmentSummary?: string;
  sql?: string;
  explanation?: string;
  type?: "segment" | "error" | "info" | "campaign_sent" | "draft";
  draftMessage?: string;
  draftSubject?: string;
}

interface CampaignStats {
  total_sent: number;
  pending: number;
  sent: number;
  delivered: number;
  read: number;
  failed: number;
  campaign_id: number | null;
  campaign_name: string | null;
}

interface CampaignHistory {
  id: number;
  name: string;
  audience_size: number;
  status: string;
  channel: string;
  created_at: string;
}

// ==========================================
//  Config
// ==========================================

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ==========================================
//  Main Page
// ==========================================

export default function Home() {
  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "👋 Welcome to Xeno CRM! I can help you find customers, create segments, and launch campaigns. Try asking me something like:\n\n• \"Find customers who spent more than ₹5000\"\n• \"Show me inactive users from Mumbai\"\n• \"Who are my top 10 customers?\"",
      timestamp: new Date(),
      type: "info",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCustomers, setSelectedCustomers] = useState<Customer[]>([]);
  const [allSelected, setAllSelected] = useState(false);

  // Campaign state
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [campaigns, setCampaigns] = useState<CampaignHistory[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [channel, setChannel] = useState("whatsapp");
  const [showDraft, setShowDraft] = useState(false);
  const [campaignName, setCampaignName] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isDrafting, setIsDrafting] = useState(false);

  // Refs
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // ==========================================
  //  Auto-scroll chat
  // ==========================================
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ==========================================
  //  Fetch campaigns on mount
  // ==========================================
  useEffect(() => {
    fetchCampaigns();
    fetchStats();
  }, []);

  // ==========================================
  //  Poll stats when campaign is active
  // ==========================================
  useEffect(() => {
    if (isPolling) {
      pollIntervalRef.current = setInterval(fetchStats, 3000);
      return () => {
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      };
    }
  }, [isPolling]);

  // ==========================================
  //  API Calls
  // ==========================================

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
        // Stop polling if all messages are in terminal state
        if (data.total_sent > 0 && data.pending === 0 && data.sent === 0) {
          setIsPolling(false);
        }
      }
    } catch (e) {
      // silently fail — stats are non-critical
    }
  };

  const fetchCampaigns = async () => {
    try {
      const res = await fetch(`${API_URL}/api/campaigns`);
      if (res.ok) {
        const data = await res.json();
        setCampaigns(data);
      }
    } catch (e) {}
  };

  const addMessage = (msg: Omit<ChatMessage, "id" | "timestamp">) => {
    const newMsg: ChatMessage = {
      ...msg,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, newMsg]);
    return newMsg;
  };

  // ==========================================
  //  Chat Handler
  // ==========================================

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    addMessage({ role: "user", content: userMessage });
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      const data = await res.json();

      if (data.type === "segment" && data.customers?.length > 0) {
        addMessage({
          role: "assistant",
          content: data.message,
          customers: data.customers,
          segmentSize: data.segment_size,
          segmentSummary: data.segment_summary,
          sql: data.sql,
          explanation: data.explanation,
          type: "segment",
        });
        setSelectedCustomers([]);
        setAllSelected(false);
      } else if (data.type === "error") {
        addMessage({
          role: "assistant",
          content: data.message,
          type: "error",
        });
      } else {
        addMessage({
          role: "assistant",
          content: data.message || "No results found.",
          sql: data.sql,
          explanation: data.explanation,
          type: "info",
        });
      }
    } catch (e) {
      addMessage({
        role: "assistant",
        content: "⚠️ Could not reach the server. Make sure the backend is running on port 8000.",
        type: "error",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // ==========================================
  //  Draft Message Handler
  // ==========================================

  const handleDraft = async () => {
    if (selectedCustomers.length === 0) return;
    setIsDrafting(true);

    try {
      const res = await fetch(`${API_URL}/api/campaign/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          segment_description: `${selectedCustomers.length} customers selected, avg spend ₹${Math.round(selectedCustomers.reduce((a, c) => a + c.total_spent, 0) / selectedCustomers.length)}`,
          channel,
        }),
      });
      const data = await res.json();
      if (data.message) {
        setDraftMessage(data.message);
        setShowDraft(true);
        setCampaignName(`Campaign ${new Date().toLocaleDateString()}`);
      }
    } catch (e) {
      addMessage({
        role: "assistant",
        content: "⚠️ Failed to draft message. Check if the backend is running and OPENROUTER_API_KEY is set.",
        type: "error",
      });
    } finally {
      setIsDrafting(false);
    }
  };

  // ==========================================
  //  Send Campaign Handler
  // ==========================================

  const handleSendCampaign = async () => {
    if (selectedCustomers.length === 0 || !draftMessage || isSending) return;
    setIsSending(true);

    try {
      const res = await fetch(`${API_URL}/api/campaign/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: campaignName || `Campaign ${Date.now()}`,
          customer_ids: selectedCustomers.map((c) => c.id),
          message_template: draftMessage,
          channel,
        }),
      });

      const data = await res.json();

      addMessage({
        role: "assistant",
        content: `🚀 Campaign "${data.campaign_name}" launched!\n\n📊 Sent to ${data.total_audience} customers\n✅ Accepted: ${data.sent}\n❌ Failed: ${data.failed}\n\nWatch the Stats panel for real-time delivery updates →`,
        type: "campaign_sent",
      });

      setShowDraft(false);
      setSelectedCustomers([]);
      setAllSelected(false);
      setIsPolling(true);
      fetchCampaigns();
      fetchStats();
    } catch (e) {
      addMessage({
        role: "assistant",
        content: "⚠️ Failed to send campaign. Make sure both the backend AND mock channel service are running.",
        type: "error",
      });
    } finally {
      setIsSending(false);
    }
  };

  // ==========================================
  //  Customer Selection
  // ==========================================

  const toggleCustomer = (customer: Customer) => {
    setSelectedCustomers((prev) => {
      const exists = prev.find((c) => c.id === customer.id);
      if (exists) return prev.filter((c) => c.id !== customer.id);
      return [...prev, customer];
    });
  };

  const toggleSelectAll = (customers: Customer[]) => {
    if (allSelected) {
      setSelectedCustomers([]);
      setAllSelected(false);
    } else {
      setSelectedCustomers(customers);
      setAllSelected(true);
    }
  };

  const lastSegmentCustomers =
    [...messages].reverse().find((m) => m.type === "segment")?.customers || [];

  // ==========================================
  //  Render
  // ==========================================

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg-primary)" }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-white text-sm"
            style={{ background: "var(--gradient-1)" }}
          >
            X
          </div>
          <div>
            <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
              Xeno CRM
            </h1>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              AI-Powered Campaign Manager
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {isPolling && (
            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--success)" }}>
              <span className="w-2 h-2 rounded-full pulse-dot" style={{ background: "var(--success)" }} />
              Live tracking
            </div>
          )}
          <div
            className="px-3 py-1.5 rounded-lg text-xs font-medium"
            style={{ background: "var(--accent-glow)", color: "var(--accent)" }}
          >
            Chat-to-Campaign
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT: Chat Panel */}
        <div className="flex-1 flex flex-col min-w-0" style={{ maxWidth: "60%" }}>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`fade-in flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${msg.role === "user" ? "rounded-br-md" : "rounded-bl-md"}`}
                  style={{
                    background: msg.role === "user" ? "var(--accent)" : "var(--bg-card)",
                    border: msg.role === "user" ? "none" : "1px solid var(--border)",
                    color: "var(--text-primary)",
                  }}
                >
                  {/* Message content */}
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>

                  {/* SQL badge */}
                  {msg.sql && (
                    <details className="mt-2">
                      <summary
                        className="text-xs cursor-pointer font-medium"
                        style={{ color: "var(--text-muted)" }}
                      >
                        View SQL query
                      </summary>
                      <pre
                        className="mt-1 p-2 rounded-lg text-xs overflow-x-auto"
                        style={{ background: "var(--bg-primary)", color: "var(--accent-hover)" }}
                      >
                        {msg.sql}
                      </pre>
                      {msg.explanation && (
                        <p className="mt-1 text-xs italic" style={{ color: "var(--text-muted)" }}>
                          {msg.explanation}
                        </p>
                      )}
                    </details>
                  )}

                  {/* Segment summary */}
                  {msg.segmentSummary && (
                    <div
                      className="mt-2 p-2 rounded-lg text-xs"
                      style={{ background: "var(--accent-glow)", color: "var(--text-secondary)" }}
                    >
                      💡 {msg.segmentSummary}
                    </div>
                  )}

                  {/* Customer cards */}
                  {msg.customers && msg.customers.length > 0 && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                          {msg.segmentSize} customers found
                        </span>
                        <button
                          onClick={() => toggleSelectAll(msg.customers!)}
                          className="text-xs font-medium px-2 py-1 rounded-md transition-all hover:opacity-80"
                          style={{ background: "var(--accent-glow)", color: "var(--accent)" }}
                        >
                          {allSelected ? "Deselect All" : "Select All"}
                        </button>
                      </div>
                      <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                        {msg.customers.map((customer) => (
                          <div
                            key={customer.id}
                            onClick={() => toggleCustomer(customer)}
                            className="flex items-center gap-3 p-2.5 rounded-xl cursor-pointer transition-all"
                            style={{
                              background: selectedCustomers.find((c) => c.id === customer.id)
                                ? "var(--accent-glow)"
                                : "var(--bg-input)",
                              border: selectedCustomers.find((c) => c.id === customer.id)
                                ? "1px solid var(--accent)"
                                : "1px solid transparent",
                            }}
                          >
                            {/* Checkbox */}
                            <div
                              className="w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all"
                              style={{
                                borderColor: selectedCustomers.find((c) => c.id === customer.id)
                                  ? "var(--accent)"
                                  : "var(--border)",
                                background: selectedCustomers.find((c) => c.id === customer.id)
                                  ? "var(--accent)"
                                  : "transparent",
                              }}
                            >
                              {selectedCustomers.find((c) => c.id === customer.id) && (
                                <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                                  <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="2" strokeLinecap="round" />
                                </svg>
                              )}
                            </div>

                            {/* Avatar */}
                            <div
                              className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                              style={{ background: "var(--gradient-1)", color: "white" }}
                            >
                              {customer.name?.charAt(0) || "?"}
                            </div>

                            {/* Info */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between">
                                <span className="text-sm font-medium truncate">{customer.name}</span>
                                <span className="text-xs font-semibold" style={{ color: "var(--success)" }}>
                                  ₹{customer.total_spent?.toLocaleString() || 0}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
                                <span>{customer.city}</span>
                                <span>•</span>
                                <span>{customer.order_count || 0} orders</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex justify-start fade-in">
                <div
                  className="rounded-2xl rounded-bl-md px-4 py-3"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
                >
                  <div className="flex items-center gap-1">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Draft Message Panel */}
          {showDraft && (
            <div
              className="mx-4 mb-2 p-4 rounded-xl fade-in"
              style={{ background: "var(--bg-card)", border: "1px solid var(--accent)" }}
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  ✉️ Draft Message
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: "var(--accent-glow)", color: "var(--accent)" }}
                  >
                    {channel}
                  </span>
                </h3>
                <button
                  onClick={() => setShowDraft(false)}
                  className="text-xs hover:opacity-70"
                  style={{ color: "var(--text-muted)" }}
                >
                  ✕
                </button>
              </div>
              <input
                type="text"
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
                placeholder="Campaign name..."
                className="w-full px-3 py-2 rounded-lg text-sm mb-2 outline-none"
                style={{ background: "var(--bg-input)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              />
              <textarea
                value={draftMessage}
                onChange={(e) => setDraftMessage(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 rounded-lg text-sm resize-none outline-none"
                style={{ background: "var(--bg-input)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              />
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {draftMessage.length} chars • {selectedCustomers.length} recipients
                </span>
                <button
                  onClick={handleSendCampaign}
                  disabled={isSending}
                  className="px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:opacity-90 disabled:opacity-50"
                  style={{ background: "var(--gradient-1)" }}
                >
                  {isSending ? "Sending..." : "🚀 Launch Campaign"}
                </button>
              </div>
            </div>
          )}

          {/* Action Bar (when customers selected) */}
          {selectedCustomers.length > 0 && !showDraft && (
            <div
              className="mx-4 mb-2 p-3 rounded-xl flex items-center justify-between fade-in"
              style={{ background: "var(--bg-card)", border: "1px solid var(--accent)" }}
            >
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                <strong style={{ color: "var(--accent)" }}>{selectedCustomers.length}</strong> customers selected
              </span>
              <div className="flex items-center gap-2">
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  className="text-xs px-2 py-1.5 rounded-lg outline-none"
                  style={{ background: "var(--bg-input)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                >
                  <option value="whatsapp">WhatsApp</option>
                  <option value="sms">SMS</option>
                  <option value="email">Email</option>
                </select>
                <button
                  onClick={handleDraft}
                  disabled={isDrafting}
                  className="px-4 py-1.5 rounded-lg text-sm font-medium text-white transition-all hover:opacity-90 disabled:opacity-50"
                  style={{ background: "var(--gradient-2)" }}
                >
                  {isDrafting ? "Drafting..." : "✍️ Draft Message"}
                </button>
              </div>
            </div>
          )}

          {/* Input */}
          <div className="p-4 border-t" style={{ borderColor: "var(--border)" }}>
            <div
              className="flex items-center gap-2 p-1 rounded-xl"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask about your customers... e.g. 'Find top spenders in Mumbai'"
                className="flex-1 px-4 py-3 bg-transparent outline-none text-sm"
                style={{ color: "var(--text-primary)" }}
                disabled={isLoading}
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="px-4 py-2.5 rounded-lg font-medium text-sm text-white transition-all hover:opacity-90 disabled:opacity-30 mr-1"
                style={{ background: "var(--gradient-1)" }}
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT: Stats Panel */}
        <div
          className="flex flex-col overflow-y-auto p-4 space-y-4"
          style={{
            width: "40%",
            borderLeft: "1px solid var(--border)",
            background: "var(--bg-secondary)",
          }}
        >
          {/* Stats Header */}
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              📊 Campaign Dashboard
            </h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
              Real-time delivery tracking
            </p>
          </div>

          {/* Stats Cards */}
          {stats && stats.campaign_name ? (
            <>
              <div
                className="p-3 rounded-xl"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                    {stats.campaign_name}
                  </span>
                  {isPolling && (
                    <span className="flex items-center gap-1 text-xs" style={{ color: "var(--success)" }}>
                      <span className="w-1.5 h-1.5 rounded-full pulse-dot" style={{ background: "var(--success)" }} />
                      Live
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <StatCard label="Total Sent" value={stats.total_sent} color="var(--accent)" />
                  <StatCard label="Delivered" value={stats.delivered} color="var(--success)" />
                  <StatCard label="Read" value={stats.read} color="var(--info)" />
                  <StatCard label="Failed" value={stats.failed} color="var(--error)" />
                </div>
              </div>

              {/* Progress Bar */}
              {stats.total_sent > 0 && (
                <div
                  className="p-3 rounded-xl"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                      Delivery Progress
                    </span>
                    <span className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>
                      {Math.round(((stats.delivered + stats.read) / stats.total_sent) * 100)}%
                    </span>
                  </div>
                  <div
                    className="h-3 rounded-full overflow-hidden flex"
                    style={{ background: "var(--bg-primary)" }}
                  >
                    <div
                      className="h-full transition-all duration-500"
                      style={{
                        width: `${(stats.read / stats.total_sent) * 100}%`,
                        background: "var(--info)",
                      }}
                    />
                    <div
                      className="h-full transition-all duration-500"
                      style={{
                        width: `${(stats.delivered / stats.total_sent) * 100}%`,
                        background: "var(--success)",
                      }}
                    />
                    <div
                      className="h-full transition-all duration-500"
                      style={{
                        width: `${(stats.sent / stats.total_sent) * 100}%`,
                        background: "var(--warning)",
                      }}
                    />
                    <div
                      className="h-full transition-all duration-500"
                      style={{
                        width: `${(stats.failed / stats.total_sent) * 100}%`,
                        background: "var(--error)",
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-3 mt-2 flex-wrap">
                    <LegendDot color="var(--info)" label="Read" />
                    <LegendDot color="var(--success)" label="Delivered" />
                    <LegendDot color="var(--warning)" label="Sent" />
                    <LegendDot color="var(--error)" label="Failed" />
                  </div>
                </div>
              )}
            </>
          ) : (
            <div
              className="p-6 rounded-xl text-center"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <div className="text-3xl mb-2">📭</div>
              <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                No campaigns yet
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                Use the chat to find customers, then launch a campaign
              </p>
            </div>
          )}

          {/* Campaign History */}
          <div>
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
              Campaign History
            </h3>
            {campaigns.length === 0 ? (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                No campaigns launched yet.
              </p>
            ) : (
              <div className="space-y-2">
                {campaigns.map((c) => (
                  <div
                    key={c.id}
                    className="p-3 rounded-xl cursor-pointer transition-all hover:opacity-80"
                    style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
                    onClick={() => {
                      // Fetch stats for this campaign
                      fetch(`${API_URL}/api/stats?campaign_id=${c.id}`)
                        .then((r) => r.json())
                        .then(setStats);
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{c.name}</span>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{
                          background:
                            c.status === "COMPLETED"
                              ? "rgba(16,185,129,0.15)"
                              : c.status === "SENDING"
                                ? "rgba(245,158,11,0.15)"
                                : "rgba(239,68,68,0.15)",
                          color:
                            c.status === "COMPLETED"
                              ? "var(--success)"
                              : c.status === "SENDING"
                                ? "var(--warning)"
                                : "var(--error)",
                        }}
                      >
                        {c.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                      <span>👥 {c.audience_size}</span>
                      <span>📱 {c.channel}</span>
                      <span>{new Date(c.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* How it works */}
          <div
            className="p-4 rounded-xl mt-auto"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
          >
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
              ⚡ How It Works
            </h3>
            <div className="space-y-2 text-xs" style={{ color: "var(--text-muted)" }}>
              <div className="flex items-start gap-2">
                <span className="flex-shrink-0">1️⃣</span>
                <span><strong style={{ color: "var(--text-secondary)" }}>Ask</strong> — Describe your target audience in plain English</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="flex-shrink-0">2️⃣</span>
                <span><strong style={{ color: "var(--text-secondary)" }}>Select</strong> — Review and select customers from the results</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="flex-shrink-0">3️⃣</span>
                <span><strong style={{ color: "var(--text-secondary)" }}>Draft</strong> — AI generates a personalized message</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="flex-shrink-0">4️⃣</span>
                <span><strong style={{ color: "var(--text-secondary)" }}>Launch</strong> — Send and track delivery in real-time</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==========================================
//  Sub-Components
// ==========================================

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      className="p-3 rounded-lg text-center"
      style={{ background: "var(--bg-primary)" }}
    >
      <div className="text-2xl font-bold count-up" style={{ color }}>
        {value}
      </div>
      <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
        {label}
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1">
      <span className="w-2 h-2 rounded-full" style={{ background: color }} />
      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>
    </div>
  );
}
