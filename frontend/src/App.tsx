import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { AgentWorkspace } from './pages/AgentWorkspace';
import { VerificationEvals } from './pages/VerificationEvals';
import { ObservabilityCost } from './pages/ObservabilityCost';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<AgentWorkspace />} />
          <Route path="verification" element={<VerificationEvals />} />
          <Route path="observability" element={<ObservabilityCost />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
