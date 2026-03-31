import re

file_path = 'C:/Users/princ/Desktop/ai survilence system/AI-Surveillance/frontend/src/App.jsx'
with open(file_path, 'r') as f:
    text = f.read()

# Replace endpoint
text = text.replace('/alerts', '/events')

# Replace component state variables
text = text.replace('alertHistory', 'events')
text = text.replace('setAlertHistory', 'setEvents')
text = text.replace('fetchAlertHistory', 'fetchEvents')
text = text.replace('setEvents(data.alerts || [])', 'setEvents(data || [])')

# Add TimelineBar component
timeline_comp = """
function TimelineBar({ events }) {
  if (!events || events.length === 0) return null;

  return (
    <div className="timeline-bar-container">
      <p className="meta-row" style={{margin: '0 0 10px'}}><strong>Live Event Timeline</strong></p>
      <div className="timeline-line">
        {events.map((evt, idx) => {
          // Normalize position when length is small to avoid stacking to the left initially
          const position = events.length > 1 ? (idx / (events.length - 1)) * 100 : 50; 
          return (
            <div 
               key={idx} 
               className={`timeline-marker marker-${evt.severity}`}
               style={{ left: `${position}%` }}
               title={`${evt.time} [ ${evt.event_type || evt.type} ]: ${evt.message}`}
               onClick={() => alert(`Time: ${evt.time}\\nType: ${evt.event_type || evt.type}\\nSeverity: ${evt.severity}\\nMessage: ${evt.message}`)}
            ></div>
          );
        })}
      </div>
    </div>
  );
}
"""

if "function TimelineBar" not in text:
    text = text.replace("function App() {", timeline_comp + "\nfunction App() {")

# Patch the UI render block properly. We'll search for the existing card manually.

old_article = """        <article className="card">
          <div className="card-header">
            <h2>Recent Security Alerts</h2>
            <span className="chip">History</span>
          </div>
          
          <div className="alert-history-list">
            {events.length === 0 ? (
              <p className="meta-row">No alerts recorded yet.</p>
            ) : (
              events.slice().reverse().map((hist, idx) => (
                <div key={idx} className={`history-item history-${hist.severity}`}>
                  <span className="history-time">{hist.time}</span>
                  <span className="history-msg">{hist.message}</span>
                </div>
              ))
            )}
          </div>
        </article>"""

new_article = """        <article className="card">
          <div className="card-header">
            <h2>Timeline & Events</h2>
            <span className="chip">History</span>
          </div>
          
          <TimelineBar events={events} />

          <div className="alert-history-list">
            {events.length === 0 ? (
              <p className="meta-row">No events recorded yet.</p>
            ) : (
              events.slice().reverse().map((hist, idx) => (
                <div key={idx} className={`history-item history-${hist.severity}`}>
                  <span className="history-time">{hist.time}</span>
                  <span className="history-type">{hist.event_type || hist.type || 'EVENT'}</span>
                  <span className="history-msg">{hist.message}</span>
                </div>
              ))
            )}
          </div>
        </article>"""

text = text.replace(old_article, new_article)

with open(file_path, 'w') as f:
    f.write(text)

print("Patched!")
