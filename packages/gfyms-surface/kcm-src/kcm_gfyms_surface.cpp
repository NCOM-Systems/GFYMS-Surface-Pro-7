#include <KQuickConfigModule>
#include <KPluginFactory>
#include <QFile>

class GfymsSurfaceConfig : public KQuickConfigModule
{
    Q_OBJECT
public:
    explicit GfymsSurfaceConfig(QObject *parent, const KPluginMetaData &metaData)
        : KQuickConfigModule(parent, metaData) {}

    Q_INVOKABLE QString productName() const
    {
        return readFile(QStringLiteral("/sys/class/dmi/id/product_name"), QStringLiteral("Unknown"));
    }

    Q_INVOKABLE QString kernelVersion() const
    {
        return readFile(QStringLiteral("/proc/sys/kernel/osrelease"), QStringLiteral("Unknown"));
    }

    Q_INVOKABLE bool isSurfacePro7() const
    {
        return productName().contains(QStringLiteral("Surface Pro 7"), Qt::CaseInsensitive);
    }

private:
    static QString readFile(const QString &path, const QString &fallback)
    {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly | QIODevice::Text))
            return fallback;
        const QString value = QString::fromUtf8(file.readAll()).trimmed();
        return value.isEmpty() ? fallback : value;
    }
};

K_PLUGIN_CLASS_WITH_JSON(GfymsSurfaceConfig, "kcm_gfyms_surface.json")
#include "kcm_gfyms_surface.moc"
