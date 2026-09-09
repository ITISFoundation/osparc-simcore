/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Mixin that patches qx.ui.core.scroll.ScrollBar to render a clean, minimal
 * scrollbar app-wide: no step buttons and no border around the track.
 *
 * qooxdoo creates the step buttons as plain qx.ui.form.RepeatButton and the
 * track as a qx.ui.core.scroll.ScrollSlider with the default "button"/"slider"
 * appearances, so the theme's "scrollbar/*" overrides never reach them. This
 * forces the scrollbar-scoped appearances (and drops the track border) instead.
 *
 * Apply once at startup with:
 *   qx.Class.patch(qx.ui.core.scroll.ScrollBar, osparc.wrapper.MScrollBar);
 */
qx.Mixin.define("osparc.wrapper.MScrollBar", {
  members: {
    // overridden
    _createChildControlImpl: function(id, hash) {
      const control = this.base(arguments, id, hash);
      if (id === "button-begin" || id === "button-end") {
        control.setAppearance("scrollbar/button");
      } else if (id === "slider") {
        // the base "slider" appearance draws a border around the track;
        // switch to the (borderless) "scrollbar/slider" one and drop the
        // border decorator that was already applied at construction
        control.setAppearance("scrollbar/slider");
        control.setDecorator(null);
      }
      return control;
    }
  }
});
