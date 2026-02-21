import { useState } from "react";

type ImageProps = {
    className?: string;
    src: string;
    alt: string;
    width?: number;
    height?: number;
};

const Image = ({ className, src, alt, width, height }: ImageProps) => {
    const [loaded, setLoaded] = useState(false);

    return (
        <img
            className={`transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"} ${className || ""}`}
            src={src}
            alt={alt}
            width={width}
            height={height}
            onLoad={() => setLoaded(true)}
        />
    );
};

export default Image;
