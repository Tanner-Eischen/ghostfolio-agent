import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { Strategy } from './pages/Strategy';
import { ToolLibrary } from './pages/ToolLibrary';
import { Verification } from './pages/Verification';
import { Observability } from './pages/Observability';
import { Evaluations } from './pages/Evaluations';
import { Finances } from './pages/Finances';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="strategy" element={<Strategy />} />
          <Route path="tools" element={<ToolLibrary />} />
          <Route path="verification" element={<Verification />} />
          <Route path="observability" element={<Observability />} />
          <Route path="evaluations" element={<Evaluations />} />
          <Route path="finances" element={<Finances />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
