import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { Toaster } from 'sonner';
import { WebSocketProvider } from './lib/websocket';
import { Layout } from './pages/Layout';
import { Dashboard } from './pages/Dashboard';
import { DlqView } from './components/DlqView';

export default function App() {
  return (
    <div data-theme="dim" className="size-full bg-base-100 text-base-content">
      <WebSocketProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/dlq" element={<DlqView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster theme="dark" position="bottom-right" richColors />
      </WebSocketProvider>
    </div>
  );
}
