/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Widget containing a JsonTreeViewer dom element
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let jsonTreeWidget = new osparc.component.widget.JsonTreeWidget(data);
 *   this.getRoot().add(jsonTreeWidget);
 * </pre>
 */

qx.Class.define("osparc.component.widget.JsonTreeWidget", {
  extend: qx.ui.basic.Label,

  /**
   * @param data {Object} Json object to be displayed by JsonTreeViewer
   */
  construct: function(data) {
    const prettyJson = JSON.stringify(data, null, "&emsp;").replace(/\n/ig, "<br>");
    this.base(arguments, prettyJson);
    this.set({
      rich: true
    });
  }
});
