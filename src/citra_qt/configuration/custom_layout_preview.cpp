// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

#include <algorithm>
#include <cmath>
#include <QMouseEvent>
#include <QPainter>
#include <QPalette>
#include "citra_qt/configuration/custom_layout_preview.h"

namespace {
// the 3DS screens: 400x240 and 320x240
constexpr double TopAspect = 400.0 / 240.0;
constexpr double BottomAspect = 320.0 / 240.0;
constexpr int HandleSize = 10;
constexpr int MinScreenSize = 40;
} // namespace

CustomLayoutPreview::CustomLayoutPreview(QWidget* parent) : QWidget(parent) {
    setMouseTracking(true);
    setMinimumHeight(160);
    QSizePolicy policy(QSizePolicy::Expanding, QSizePolicy::Preferred);
    policy.setHeightForWidth(true);
    setSizePolicy(policy);
    setToolTip(tr("Drag a screen to move it. Drag its corner to resize it; hold Shift to keep its "
                  "shape."));
}

void CustomLayoutPreview::SetRect(Screen screen, const QRect& rect) {
    if (rects[screen] == rect) {
        return;
    }
    rects[screen] = rect;
    update();
}

QSize CustomLayoutPreview::sizeHint() const {
    return {480, heightForWidth(480)};
}

int CustomLayoutPreview::heightForWidth(int width) const {
    const QSize c = Canvas();
    return std::clamp(static_cast<int>(width * c.height() / static_cast<double>(c.width())), 160,
                      420);
}

QSize CustomLayoutPreview::Canvas() const {
    if (dragging >= 0) {
        return canvas_at_grab;
    }
    // a 16:9 window big enough for both screens, at least 1280x720
    int w = 1280;
    int h = 720;
    for (const QRect& r : rects) {
        w = std::max(w, r.right() + 1);
        h = std::max(h, r.bottom() + 1);
    }
    w = std::max(w, h * 16 / 9);
    h = std::max(h, w * 9 / 16);
    return {w, h};
}

double CustomLayoutPreview::Scale() const {
    const QSize c = Canvas();
    return std::min((width() - 2) / static_cast<double>(c.width()),
                    (height() - 2) / static_cast<double>(c.height()));
}

QRectF CustomLayoutPreview::ToWidget(const QRect& r) const {
    const double s = Scale();
    return {1 + r.x() * s, 1 + r.y() * s, r.width() * s, r.height() * s};
}

QRectF CustomLayoutPreview::CornerHandle(Screen screen) const {
    const QRectF r = ToWidget(rects[screen]);
    return {r.right() - HandleSize, r.bottom() - HandleSize, HandleSize, HandleSize};
}

void CustomLayoutPreview::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    const QPalette& pal = palette();

    const QSize c = Canvas();
    const double s = Scale();
    const QRectF window{1, 1, c.width() * s, c.height() * s};
    p.setPen(QPen(pal.color(QPalette::Mid), 1));
    p.setBrush(QColor(0, 0, 0));
    p.drawRect(window);

    // the bottom screen is drawn first, like the emulator does when they overlap
    const std::array<Screen, 2> order{Bottom, Top};
    const std::array<QString, 2> names{tr("Top Screen"), tr("Bottom Screen")};
    const QColor accent = pal.color(QPalette::Highlight);
    for (const Screen sc : order) {
        const QRectF r = ToWidget(rects[sc]);
        QColor fill = sc == Top ? accent : accent.darker(160);
        fill.setAlpha(dragging == sc ? 230 : 190);
        p.setPen(QPen(dragging == sc ? pal.color(QPalette::BrightText) : accent.lighter(130), 1.5));
        p.setBrush(fill);
        p.drawRect(r);

        p.setPen(pal.color(QPalette::HighlightedText));
        const QString label = QStringLiteral("%1\n%2 x %3")
                                  .arg(names[sc])
                                  .arg(rects[sc].width())
                                  .arg(rects[sc].height());
        p.drawText(r, Qt::AlignCenter, label);

        p.setPen(Qt::NoPen);
        p.setBrush(pal.color(QPalette::HighlightedText));
        p.drawRect(CornerHandle(sc));
    }

    p.setPen(QColor(255, 255, 255, 140)); // the window is always drawn black
    p.drawText(window.adjusted(6, 4, -6, -4), Qt::AlignRight | Qt::AlignBottom,
               QStringLiteral("%1 x %2").arg(c.width()).arg(c.height()));
}

void CustomLayoutPreview::mousePressEvent(QMouseEvent* event) {
    if (event->button() != Qt::LeftButton) {
        return;
    }
    const QPointF pos = event->position();
    // the top screen is drawn on top, so it gets the click first
    for (const Screen sc : {Top, Bottom}) {
        const bool corner = CornerHandle(sc).adjusted(-3, -3, 3, 3).contains(pos);
        if (corner || ToWidget(rects[sc]).contains(pos)) {
            canvas_at_grab = Canvas();
            dragging = sc;
            resizing = corner;
            const double s = Scale();
            grab_offset = QPoint(static_cast<int>((pos.x() - 1) / s) - rects[sc].x(),
                                 static_cast<int>((pos.y() - 1) / s) - rects[sc].y());
            update();
            return;
        }
    }
}

void CustomLayoutPreview::mouseMoveEvent(QMouseEvent* event) {
    const QPointF pos = event->position();
    if (dragging < 0) {
        const bool on_corner =
            CornerHandle(Top).contains(pos) || CornerHandle(Bottom).contains(pos);
        setCursor(on_corner ? Qt::SizeFDiagCursor : Qt::ArrowCursor);
        return;
    }
    const Screen sc = static_cast<Screen>(dragging);
    const double s = Scale();
    const int x = static_cast<int>(std::lround((pos.x() - 1) / s));
    const int y = static_cast<int>(std::lround((pos.y() - 1) / s));
    QRect r = rects[sc];
    if (resizing) {
        int w = std::max(MinScreenSize, x - r.x());
        int h = std::max(MinScreenSize, y - r.y());
        if (event->modifiers() & Qt::ShiftModifier) {
            const double aspect = sc == Top ? TopAspect : BottomAspect;
            h = static_cast<int>(std::lround(w / aspect));
        }
        r.setSize({w, h});
    } else {
        r.moveTo(std::max(0, x - grab_offset.x()), std::max(0, y - grab_offset.y()));
    }
    if (r != rects[sc]) {
        rects[sc] = r;
        update();
        emit RectChanged(sc, r);
    }
}

void CustomLayoutPreview::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton && dragging >= 0) {
        dragging = -1;
        updateGeometry();
        update();
    }
}
