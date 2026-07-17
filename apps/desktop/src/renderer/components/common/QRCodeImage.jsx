import { useEffect, useState } from "react";
import QRCode from "qrcode";

export function QRCodeImage({ value, alt }) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    let active = true;
    if (!value) {
      setSrc("");
      return () => {
        active = false;
      };
    }
    QRCode.toDataURL(value, {
      margin: 1,
      scale: 6,
      errorCorrectionLevel: "M"
    })
      .then((dataUrl) => {
        if (active) {
          setSrc(dataUrl);
        }
      })
      .catch(() => {
        if (active) {
          setSrc("");
        }
      });
    return () => {
      active = false;
    };
  }, [value]);

  if (!src) {
    return <div className="payment-qr-placeholder" aria-hidden="true" />;
  }

  return <img src={src} alt={alt} />;
}
