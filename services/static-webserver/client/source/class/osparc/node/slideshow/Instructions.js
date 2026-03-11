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

qx.Class.define("osparc.node.slideshow.Instructions", {
  type: "static",

  statics: {
    WIDTH: 600,
    MIN_HEIGHT: 200,
    popUpInWindow: function(node) {
      const instructions = node.getSlideshowInstructions();
      if (instructions) {
        const markdownInstructions = new osparc.ui.markdown.Markdown().set({
          value: instructions,
          padding: 3,
          font: "text-14"
        });
        const title = node.getLabel();
        const win = osparc.ui.window.Window.popUpInWindow(markdownInstructions, title, this.WIDTH, this.MIN_HEIGHT).set({
          modal: false,
          clickAwayClose: false
        });
        markdownInstructions.addListener("resized", () => win.center());

        win.getContentElement().setStyles({
          "border-color": qx.theme.manager.Color.getInstance().resolve("strong-main")
        });

        win.center();
        return win;
      }
      return null;
    },
  },
});
