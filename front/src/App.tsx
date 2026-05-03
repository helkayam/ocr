import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import WorkspaceDetails from "./pages/WorkspaceDetails";
import WorkspaceCreate from "./pages/WorkspaceCreate";
import MapView from "./pages/MapView";
import SensorsView from "./pages/SensorsView";
import ReportView from "./pages/ReportView";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner
        theme="dark"
        position="top-right"
        toastOptions={{
          style: {
            background: 'hsl(0 0% 12%)',
            border: '1px solid hsl(0 0% 20%)',
            color: 'hsl(0 0% 100%)',
          },
          className: 'sonner-toast',
        }}
      />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/workspace/:id" element={<WorkspaceDetails />} />
          <Route path="/workspace/:id/map" element={<MapView />} />
          <Route path="/workspace/:id/sensors" element={<SensorsView />} />
          <Route path="/workspace/:id/report" element={<ReportView />} />
          <Route path="/create" element={<WorkspaceCreate />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
