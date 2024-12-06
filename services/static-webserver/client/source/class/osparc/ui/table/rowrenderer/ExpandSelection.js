/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.table.rowrenderer.ExpandSelection", {
  extend: qx.ui.table.rowrenderer.Default,

  construct: function(_, expandableColPos = 2) {
    this.base(arguments);

    this.__expandableColPos = expandableColPos;
  },

  members: {
    __expandableColPos: null,

    // overridden
    updateDataRowElement : function(rowInfo, rowElem) {
      this.base(arguments, rowInfo, rowElem);

      const style = rowElem.style;

      const rowClicked = () => {
        // switch it's expanded if it was already expanded
        rowInfo.expanded = !rowInfo.expanded;

        const messageDiv = rowElem.children.item(this.__expandableColPos);
        const expandedHeight = messageDiv.scrollHeight;
        const newHeight = (rowInfo.expanded ? expandedHeight : 19) + "px";
        style.height = newHeight
        Array.from(rowElem.children).forEach(child => child.style.height = newHeight);
      }
      rowElem.removeEventListener("click", rowClicked);
      rowElem.addEventListener("click", rowClicked);
    }
  }
});
