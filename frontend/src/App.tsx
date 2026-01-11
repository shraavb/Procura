import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import Dashboard from './pages/Dashboard'
import BOMs from './pages/BOMs'
import BOMDetail from './pages/BOMDetail'
import Suppliers from './pages/Suppliers'
import PurchaseOrders from './pages/PurchaseOrders'
import PODetail from './pages/PODetail'
import Settings from './pages/Settings'
import ToastContainer from './components/common/Toast'

function App() {
  return (
    <BrowserRouter>
      <ToastContainer />
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="boms" element={<BOMs />} />
          <Route path="boms/:id" element={<BOMDetail />} />
          <Route path="suppliers" element={<Suppliers />} />
          <Route path="pos" element={<PurchaseOrders />} />
          <Route path="pos/:id" element={<PODetail />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
