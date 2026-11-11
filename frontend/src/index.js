import React from 'react';
import ReactDOM from 'react-dom/client';
import IntentLockApp from './intentlock/IntentLockApp';

// Netrava IntentLock is the application. The earlier MuleCatch screens remain in the repository but are not loaded.
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <IntentLockApp />
  </React.StrictMode>
);
