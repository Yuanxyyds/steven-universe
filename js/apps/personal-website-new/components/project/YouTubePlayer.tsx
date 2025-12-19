"use client";

import React from "react";
import ReactPlayer from "react-player";

interface YouTubePlayerProps {
  url: string;
  controls?: boolean;
  width?: string;
  height?: string;
}

export const YouTubePlayer: React.FC<YouTubePlayerProps> = ({
  url,
  controls = true,
  width = "100%",
  height = "100%",
}) => {
  return (
    <ReactPlayer
      src={url}
      controls={controls}
      width={width}
      height={height}
    />
  );
};