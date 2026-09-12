import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const routeMetadata: Record<string, { title: string; description: string }> = {
  "/dashboard": {
    title: "Tổng quan phần cứng | NeXus",
    description: "Theo dõi sức khỏe, điện áp, dòng điện và công suất của bộ NeXus theo thời gian thực.",
  },
  "/hardware": {
    title: "Sơ đồ và log phần cứng | NeXus",
    description: "Xem luồng GOOUUU ESP32-S3, INA226, L298N, JGB37-520 và log chẩn đoán realtime.",
  },
  "/doctor": {
    title: "Bác sĩ AI | NeXus",
    description: "Mô tả triệu chứng và nhận giải thích dựa trên telemetry cùng giới hạn an toàn của NeXus.",
  },
};

export function RouteMeta() {
  const { pathname } = useLocation();

  useEffect(() => {
    const metadata = routeMetadata[pathname] ?? routeMetadata["/dashboard"];
    document.title = metadata.title;
    document.documentElement.lang = "vi";
    document.querySelector<HTMLMetaElement>('meta[name="description"]')?.setAttribute(
      "content",
      metadata.description,
    );
  }, [pathname]);

  return null;
}
