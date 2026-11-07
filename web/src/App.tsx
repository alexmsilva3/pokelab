import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RotaProtegida } from '@/components/RotaProtegida'
import { Expedicoes } from '@/pages/Expedicoes'
import { Laboratorio } from '@/pages/Laboratorio'
import { Login } from '@/pages/Login'
import { Mapa } from '@/pages/Mapa'
import { Pokedex } from '@/pages/Pokedex'
import { RelatorioDeCampo } from '@/pages/RelatorioDeCampo'
import { Registro } from '@/pages/Registro'
import { Treinadores } from '@/pages/Treinadores'
import { useSessao } from '@/store/auth'

export function App() {
  return (
    <BrowserRouter>
      <Rotas />
    </BrowserRouter>
  )
}

function Rotas() {
  const sessao = useSessao()

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />
      <Route element={<RotaProtegida />}>
        <Route path="/laboratorio" element={<Laboratorio />} />
        <Route path="/pokedex" element={<Pokedex />} />
        <Route path="/treinadores" element={<Treinadores />} />
        <Route path="/mapa" element={<Mapa />} />
        <Route path="/expedicoes" element={<Expedicoes />} />
        <Route path="/expedicoes/:id/relatorio" element={<RelatorioDeCampo />} />
      </Route>
      <Route path="*" element={<Navigate to={sessao ? '/laboratorio' : '/login'} replace />} />
    </Routes>
  )
}
