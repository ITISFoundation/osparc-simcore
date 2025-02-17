/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2025 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.ui.markdown.MarkdownWindow", {
  extend: osparc.ui.window.Window,

  construct: function(markdownUrl) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.VBox(),
      resizable: true,
      showMaximize: false,
      showMinimize: false,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });

    const markdown = new osparc.ui.markdown.Markdown().set({
      padding: 15,
    });
    const scrollContainer = new qx.ui.container.Scroll();
    scrollContainer.add(markdown);
    this._add(scrollContainer, {
      flex: 1,
    });

    if (markdownUrl) {
      fetch(markdownUrl)
        .then(res => res.text())
        .then(text => markdown.setValue(text));
    }
  },
});
