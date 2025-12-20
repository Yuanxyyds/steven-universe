import { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Hongyuan (Steven) Liu | AI Developer',
    short_name: 'Steven Liu',
    description: 'Portfolio of Hongyuan (Steven) Liu, M.Eng. student at UPenn specializing in Machine Learning, Software Engineering, and UI/UX Design.',
    start_url: '/',
    display: 'standalone',
    background_color: '#000000',
    theme_color: '#ab31de',
    icons: [
      {
        src: '/favicon.png',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
  };
}
