import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { RepoAnalysis } from './pages/RepoAnalysis';
import { AgentChat } from './pages/AgentChat';
import { VerificationEvals } from './pages/VerificationEvals';
import { ObservabilityCost } from './pages/ObservabilityCost';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<RepoAnalysis />} />
          <Route path="chat" element={<AgentChat />} />
          <Route path="verification" element={<VerificationEvals />} />
          <Route path="observability" element={<ObservabilityCost />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
