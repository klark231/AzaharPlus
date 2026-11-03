// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

#pragma once

#include <array>
#include <QRect>
#include <QWidget>

/// A drag-and-drop picture of the custom layout: the two screens as boxes on the window. Drag a
/// box to move it, drag its corner to resize it (Shift keeps the 3DS aspect ratio).
class CustomLayoutPreview : public QWidget {
    Q_OBJECT

public:
    enum Screen { Top, Bottom };

    explicit CustomLayoutPreview(QWidget* parent = nullptr);

    void SetRect(Screen screen, const QRect& rect);
    QRect Rect(Screen screen) const {
        return rects[screen];
    }

    QSize sizeHint() const override;
    bool hasHeightForWidth() const override {
        return true;
    }
    int heightForWidth(int width) const override;

signals:
    /// The user moved or resized a screen
    void RectChanged(Screen screen, const QRect& rect);

protected:
    void paintEvent(QPaintEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    /// The area of the window the picture shows, in layout pixels
    QSize Canvas() const;
    double Scale() const;
    QRectF ToWidget(const QRect& r) const;
    QRectF CornerHandle(Screen screen) const;

    std::array<QRect, 2> rects{QRect{0, 0, 800, 480}, QRect{80, 480, 640, 480}};
    int dragging = -1;
    bool resizing = false;
    QPoint grab_offset;   ///< where in the box it was grabbed, in layout pixels
    QSize canvas_at_grab; ///< the canvas stays put while dragging
};
