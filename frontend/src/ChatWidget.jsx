import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './ChatWidget.css';

const AI_API_URL = import.meta.env.VITE_AI_API_URL || 'http://localhost:8000';

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: "Hi! I'm your AI Proctoring Assistant. How can I help?" }
  ]);
  const [inputStr, setInputStr] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSendMessage = async (e, quickText = null) => {
    if (e) e.preventDefault();
    const textToSend = quickText || inputStr.trim();
    if (!textToSend) return;

    // Add user message
    setMessages(prev => [...prev, { sender: 'user', text: textToSend }]);
    setInputStr('');
    setIsTyping(true);

    try {
      const response = await axios.post(`${AI_API_URL}/chat`, {
        message: textToSend
      });
      
      const botReply = response.data.reply || "Sorry, I couldn't process that.";
      setMessages(prev => [...prev, { sender: 'bot', text: botReply }]);
    } catch (err) {
      console.error("Chat API Error:", err);
      setMessages(prev => [...prev, { sender: 'bot', text: "Error connecting to AI service." }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="chat-container">
      {/* Floating Button */}
      {!isOpen && (
        <button 
          className="chat-toggle-btn"
          onClick={() => setIsOpen(true)}
          aria-label="Open Chat"
        >
          <span className="chat-icon">💬</span>
        </button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div className="chat-window">
          <div className="chat-header">
            <h3>AI Assistant</h3>
            <button className="chat-close-btn" onClick={() => setIsOpen(false)}>✕</button>
          </div>
          
          <div className="chat-messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-bubble ${msg.sender}`}>
                <div className="message-content">{msg.text}</div>
              </div>
            ))}
            {isTyping && (
              <div className="message-bubble bot">
                <div className="message-content typing">
                  <span>.</span><span>.</span><span>.</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-quick-actions">
             <button onClick={() => handleSendMessage(null, "System status")}>Status</button>
             <button onClick={() => handleSendMessage(null, "Show alerts")}>Alerts</button>
             <button onClick={() => handleSendMessage(null, "What is cheating?")}>Help</button>
          </div>

          <form className="chat-input-area" onSubmit={handleSendMessage}>
            <input 
              type="text" 
              placeholder="Ask me anything..." 
              value={inputStr}
              onChange={(e) => setInputStr(e.target.value)}
            />
            <button type="submit" disabled={!inputStr.trim() || isTyping}>
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
}