import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { m, AnimatePresence } from 'motion/react';
import { Navbar } from './Navbar';
import { WakeupBanner } from './WakeupBanner';

export const AppLayout: React.FC = () => {
  const location = useLocation();

  return (
    <div className="min-h-screen flex flex-col bg-app text-txt-primary font-sans transition-colors duration-200">
      <WakeupBanner />
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-24 md:py-8">
        <AnimatePresence mode="wait">
          <m.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <Outlet />
          </m.div>
        </AnimatePresence>
      </main>
    </div>
  );
};
