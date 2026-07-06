/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Mixin that reveals a card's menu (three-dots) button only when the card is
 * hovered, its menu is open, or when the reveal is forced (e.g. multi-selection).
 *
 * The target widget is kept in the layout and its opacity is toggled instead of
 * its visibility, so:
 *  - there is no layout reflow (which would otherwise fire a spurious pointerout),
 *  - the widget stays in the DOM and remains reachable by e2e tests and product
 *    tours that rely on its osparc-test-id.
 *
 * Consumers must:
 *  - call `_setHoverRevealWidget(widget)` once the target widget exists,
 *  - call `_evalHoverReveal()` whenever the hovered state changes,
 *  - optionally call `_keepRevealedWhileMenuOpen(menu)` to keep it visible while
 *    a menu popup is open,
 *  - optionally define `_isHoverRevealForced()` on the class to force the widget visible.
 */
qx.Mixin.define("osparc.dashboard.MShowMenuOnHover", {
  members: {
    __hoverRevealWidget: null,
    __hoverMenuOpen: false,

    _setHoverRevealWidget: function(widget) {
      this.__hoverRevealWidget = widget;
      this._evalHoverReveal();
    },

    _keepRevealedWhileMenuOpen: function(menu) {
      menu.addListener("appear", () => {
        this.__hoverMenuOpen = true;
        this._evalHoverReveal();
      });
      menu.addListener("disappear", () => {
        this.__hoverMenuOpen = false;
        this._evalHoverReveal();
      });
    },

    _evalHoverReveal: function() {
      if (!this.__hoverRevealWidget) {
        return;
      }
      // `_isHoverRevealForced` is an optional hook defined by the consuming class
      const forced = ("_isHoverRevealForced" in this) && this._isHoverRevealForced();
      const show = this.hasState("hovered") || this.__hoverMenuOpen || forced;
      // play with opacity instead of visibility to let playwright and product tours reach the widget
      this.__hoverRevealWidget.setOpacity(show ? 1 : 0);
    },
  }
});
