import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { mountToastContainer } from './hooks/useToast';

// Mount toast portal before React app so toasts are always available
mountToastContainer();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
