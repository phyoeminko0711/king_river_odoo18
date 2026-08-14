/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

function openUrl(url) {
    window.open(url, "_blank", "noopener");
}

async function copyLink(url) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(url);
        return true;
    }
    return false;
}

class ViberShareFallbackDialog extends Component {
    static template = "workshop_job_card.ViberShareFallbackDialog";
    static components = { Dialog };
    static props = ["close", "title", "message", "url", "downloadUrl"];

    openPdf() {
        openUrl(this.props.url);
        this.props.close();
    }

    async copyLink() {
        const copied = await copyLink(this.props.url).catch(() => false);
        if (!copied && this.props.url) {
            window.prompt(_t("Copy Job Card PDF link"), this.props.url);
        }
        this.env.services.notification.add(_t("The PDF link was copied."), {
            title: _t("Share to Viber"),
            type: "success",
        });
        this.props.close();
    }

    downloadPdf() {
        openUrl(this.props.downloadUrl);
        this.props.close();
    }
}

function showFallback(env, params) {
    env.services.dialog.add(ViberShareFallbackDialog, {
        title: params.title || _t("Share to Viber"),
        message: params.message || "",
        url: params.url,
        downloadUrl: params.download_url,
    });
}

registry.category("actions").add("workshop_job_card.share_to_viber", (env, action) => {
    const params = action.params || {};
    const notification = env.services.notification;

    if (navigator.share) {
        try {
            navigator
                .share({
                    title: params.title,
                    text: params.message,
                    url: params.url,
                })
                .catch((error) => {
                    if (error && error.name === "AbortError") {
                        return;
                    }
                    notification.add(
                        error && error.message
                            ? error.message
                            : _t("The browser could not open the native share sheet."),
                        {
                            title: _t("Share to Viber"),
                            type: "warning",
                        }
                    );
                    showFallback(env, params);
                });
            return;
        } catch (error) {
            if (error && error.name === "AbortError") {
                return;
            }
            notification.add(
                error && error.message
                    ? error.message
                    : _t("The browser could not open the native share sheet."),
                {
                    title: _t("Share to Viber"),
                    type: "warning",
                }
            );
        }
    }

    showFallback(env, params);
});
