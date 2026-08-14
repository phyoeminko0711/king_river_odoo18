/** @odoo-module **/

import {ReportAction} from "@web/webclient/actions/reports/report_action";
import {patch} from "@web/core/utils/patch";
import {loadBundle} from "@web/core/assets";

patch(ReportAction.prototype, {
    /**
     * Overriding the print method to ensure assets are loaded
     * specifically for the iframe's document before printing.
     */
    async print() {
        const iframeDoc = this.iframe.el.contentWindow.document;

        // Load bundles into the iframe document
        await this.injectBundlesIntoIframe(iframeDoc);

        // Trigger printing of iframe content
        this.iframe.el.contentWindow.print();
    },

    /**
     * Injects required bundles into the iframe's document.
     * @param {Document} iframeDoc - The iframe's document object.
     */
    async injectBundlesIntoIframe(iframeDoc) {
        // Load the bundles
        const pdfAssets = await loadBundle("web.report_assets_pdf.min.css");
        const commonAssets = await loadBundle("web.report_assets_common.min.css");

        // Inject the stylesheets and scripts into the iframe
        const injectAssets = (assets) => {
            assets.forEach((asset) => {
                if (asset.endsWith(".css")) {
                    const link = iframeDoc.createElement("link");
                    link.rel = "stylesheet";
                    link.href = asset;
                    iframeDoc.head.appendChild(link);
                }
            });
        };

        injectAssets(pdfAssets);
        injectAssets(commonAssets);
    },
});
