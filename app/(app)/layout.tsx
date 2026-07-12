import { Sidebar } from "@/components/ananta/sidebar";
import { MobileNavProvider } from "@/components/ananta/nav-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <MobileNavProvider>
      <div className="flex">
        <Sidebar />
        {/* min-w-0 wajib: tanpa ini flex child menolak menyusut & tabel lebar
            memaksa seluruh halaman geser horizontal di layar sempit. */}
        <div className="app-main min-w-0 flex-1">{children}</div>
      </div>
    </MobileNavProvider>
  );
}
