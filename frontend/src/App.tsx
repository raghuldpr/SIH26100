import React from 'react';

export const App: React.FC = () => {
  return (
    <main className="container">
      <h1 className="title">SIH26100</h1>
      <p className="subtitle">Bid Compliance Verification Platform</p>
      <div className="status-badge">
        <span className="status-dot" aria-hidden="true"></span>
        <span>Frontend is running.</span>
      </div>
    </main>
  );
};

export default App;
