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
 * Patches qx.ui.basic.Image so font icons keep their intended size.
 *
 * Font icons carry their size as a source postfix (e.g. "@FontAwesomeSolid/globe/16").
 * qooxdoo sizes them correctly on first render, but qx.ui.basic.Image._applyDimension
 * re-derives the font size on every re-layout from either the font's default size
 * (scale off) or a scale computation (scale on), ignoring the postfix. This is triggered
 * app-wide when switching theme (a live color-theme swap re-applies appearances), making
 * sized font icons render at the wrong size.
 *
 * This re-asserts the postfix size after the original runs. Font icons without a size
 * postfix (which legitimately rely on "scale") are left untouched.
 *
 * Note: this is a manual monkey-patch instead of qx.Class.patch on purpose. qooxdoo
 * transpiles the original _applyDimension's super-call to
 * "qx.ui.basic.Image.prototype._applyDimension.base.call(this)". qx.Class.patch replaces
 * that prototype method with a wrapper that has no ".base", which breaks the original's
 * super-call. Assigning the method directly while preserving ".base" avoids that.
 *
 * Apply once at startup with:
 *   osparc.wrapper.ImageFontIcon.patch();
 */
qx.Class.define("osparc.wrapper.ImageFontIcon", {
  type: "static",

  statics: {
    patch: function() {
      const proto = qx.ui.basic.Image.prototype;
      if (proto.$$fontIconPatched) {
        return;
      }

      // eslint-disable-next-line no-underscore-dangle
      const origApplyDimension = proto._applyDimension;
      const patched = function() {
        origApplyDimension.call(this);

        const source = this.getSource();
        if (source && source.startsWith("@")) {
          const parts = source.split("/");
          const postfixSize = parts.length > 2 ? parseInt(parts[2], 10) : NaN;
          if (!isNaN(postfixSize)) {
            const el = this.getContentElement();
            if (el) {
              el.setStyle("fontSize", postfixSize + "px");
            }
          }
        }
      };
      // preserve the base reference so the original's own super-call keeps working
      patched.base = origApplyDimension.base;
      patched.self = origApplyDimension.self;

      // eslint-disable-next-line no-underscore-dangle
      proto._applyDimension = patched;
      proto.$$fontIconPatched = true;
    }
  }
});
