import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Laboratorio } from '@/pages/Laboratorio'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/laboratorio" element={<Laboratorio />} />
        <Route path="*" element={<Navigate to="/laboratorio" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
