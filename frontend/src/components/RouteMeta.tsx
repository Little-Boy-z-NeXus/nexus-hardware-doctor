import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useI18n } from "../i18n/I18nContext";

const routeMetadata: Record<string, { title: [string, string]; description: [string, string] }> = {
  "/dashboard": {
    title: ["Hardware Overview | NeXus", "Tổng quan phần cứng | NeXus"],
    description: ["Monitor NeXus health, voltage, current, and power in real time.", "Theo dõi sức khỏe, điện áp, dòng điện và công suất của bộ NeXus theo thời gian thực."],
  },
  "/hardware": {
    title: ["Hardware Graph and Logs | NeXus", "Sơ đồ và log phần cứng | NeXus"],
    description: ["Inspect the active hardware profile, connections, signals, and real-time diagnostic logs.", "Xem hardware profile đang chọn, kết nối, tín hiệu và log chẩn đoán realtime."],
  },
  "/doctor": {
    title: ["AI Doctor | NeXus", "Bác sĩ AI | NeXus"],
    description: ["Describe a symptom and get an evidence-based explanation within NeXus safety limits.", "Mô tả triệu chứng và nhận giải thích dựa trên telemetry cùng giới hạn an toàn của NeXus."],
  },
};

export function RouteMeta() {
  const { pathname } = useLocation();
  const { language } = useI18n();

  useEffect(() => {
    const metadata = routeMetadata[pathname] ?? routeMetadata["/dashboard"];
    const index = language === "vi" ? 1 : 0;
    document.title = metadata.title[index];
    document.documentElement.lang = language;
    document.querySelector<HTMLMetaElement>('meta[name="description"]')?.setAttribute(
      "content",
      metadata.description[index],
    );
    document.querySelector<HTMLMetaElement>('meta[property="og:locale"]')?.setAttribute(
      "content",
      language === "vi" ? "vi_VN" : "en_US",
    );
    document.querySelector<HTMLMetaElement>('meta[property="og:title"]')?.setAttribute("content", metadata.title[index]);
    document.querySelector<HTMLMetaElement>('meta[property="og:description"]')?.setAttribute("content", metadata.description[index]);
    document.querySelector<HTMLMetaElement>('meta[name="twitter:title"]')?.setAttribute("content", metadata.title[index]);
    document.querySelector<HTMLMetaElement>('meta[name="twitter:description"]')?.setAttribute("content", metadata.description[index]);
  }, [language, pathname]);

  return null;
}
