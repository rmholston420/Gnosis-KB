import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full p-12 text-center">
      <span className="text-5xl mb-4">404</span>
      <h1 className="text-lg font-semibold text-gnosis-fg mb-2">Page not found</h1>
      <p className="text-gnosis-muted text-sm mb-6">The page you are looking for does not exist.</p>
      <Link to="/" className="text-gnosis-accent text-sm hover:underline">← Back to Notes</Link>
    </div>
  );
}
