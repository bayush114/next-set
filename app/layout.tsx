import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'Next Set — show up, get stronger',description:'A workout log that remembers. Offline logging, cloud sync, routines, and progress.',manifest:'/manifest.webmanifest',icons:{icon:'/icon.svg'},robots:{index:false,follow:false}};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body><div id="next-set-shell">{children}</div></body></html>}
