from decimal import Decimal
from functools import cached_property
from urllib.parse import urlencode

from django.conf import settings
from django.db import models
from django.forms.models import model_to_dict

from apps import constants as c
from apps import utils
from apps.mixin import BaseLogModel, BaseModel, SequenceMixin
from apps.sspanel.models import User


class BaseNodeModel(BaseModel):
    name = models.CharField("名字", max_length=32)
    server = models.CharField("服务器地址", help_text="支持逗号分隔传多个地址", max_length=256)
    enable = models.BooleanField("是否开启", default=True, db_index=True)

    class Meta:
        abstract = True


class ProxyNode(BaseNodeModel, SequenceMixin):

    NODE_TYPE_SS = "ss"
    NODE_TYPE_VLESS = "vless"
    NODE_TYPE_TROJAN = "trojan"
    NODE_CHOICES = (
        (NODE_TYPE_SS, NODE_TYPE_SS),
        (NODE_TYPE_VLESS, NODE_TYPE_VLESS),
        (NODE_TYPE_TROJAN, NODE_TYPE_TROJAN),
    )

    node_type = models.CharField(
        "节点类型", default=NODE_TYPE_SS, choices=NODE_CHOICES, max_length=32
    )
    info = models.CharField("节点说明", max_length=1024, blank=True)
    level = models.PositiveIntegerField(default=0)
    country = models.CharField(
        "国家", default="CN", max_length=5, choices=c.COUNTRIES_CHOICES
    )
    used_traffic = models.BigIntegerField("已用流量", default=0)
    total_traffic = models.BigIntegerField("总流量", default=settings.GB)
    enlarge_scale = models.DecimalField(
        "倍率", default=Decimal("1.0"), decimal_places=1, max_digits=10,
    )

    ehco_listen_host = models.CharField("隧道监听地址", max_length=64, blank=True, null=True)
    ehco_listen_port = models.CharField("隧道监听端口", max_length=64, blank=True, null=True)
    ehco_listen_type = models.CharField(
        "隧道监听类型", max_length=64, choices=c.LISTEN_TYPES, default=c.LISTEN_RAW
    )
    ehco_transport_type = models.CharField(
        "隧道传输类型", max_length=64, choices=c.TRANSPORT_TYPES, default=c.TRANSPORT_RAW
    )

    class Meta:
        verbose_name = "代理节点"
        verbose_name_plural = "代理节点"
        ordering = ("sequence",)

    def __str__(self) -> str:
        return f"{self.name}({self.node_type})"

    @classmethod
    def get_active_nodes(cls, sub_mode=False):
        active_nodes = list(
            cls.objects.filter(enable=True)
            .select_related("ss_config")
            .prefetch_related("relay_rules")
            .order_by("sequence")
        )
        return active_nodes

    def get_ss_node_config(self):
        configs = {"users": []}
        ss_config = self.ss_config
        for user in User.objects.filter(level__gte=self.level).values(
            "id",
            "ss_port",
            "ss_password",
            "total_traffic",
            "upload_traffic",
            "download_traffic",
        ):
            enable = self.enable and user["total_traffic"] > (
                user["download_traffic"] + user["upload_traffic"]
            )
            if ss_config.multi_user_port:
                # NOTE 单端口多用户
                port = ss_config.multi_user_port
            else:
                port = port = user.ss_port
            configs["users"].append(
                {
                    "user_id": user["id"],
                    "port": port,
                    "password": user["ss_password"],
                    "enable": enable,
                    "method": ss_config.method,
                }
            )
        return configs

    def get_proxy_configs(self):
        # TODO add cache
        if self.node_type == self.NODE_TYPE_SS:
            return self.get_ss_node_config()
        return {}

    @property
    def human_total_traffic(self):
        return utils.traffic_format(self.total_traffic)

    @property
    def human_used_traffic(self):
        return utils.traffic_format(self.used_traffic)

    @property
    def api_endpoint(self):
        params = {"token": settings.TOKEN}
        if self.node_type == self.NODE_TYPE_SS:
            return settings.HOST + f"/api/proxy_configs/{self.id}/?{urlencode(params)}"
        # TODO vless/trojan
        return ""

    @property
    def ehco_api_endpoint(self):
        params = {"token": settings.TOKEN}
        return settings.HOST + f"/api/ehco_server_config/{self.id}/?{urlencode(params)}"

    @cached_property
    def online_info(self):
        return NodeOnlineLog.get_latest_online_log_info(self.id)

    @cached_property
    def enable_relay(self):
        return bool(self.relay_rules.exists())

    @cached_property
    def enable_ehco_tunnel(self):
        return self.ehco_listen_host and self.ehco_listen_port


class SSConfig(models.Model):
    proxy_node = models.OneToOneField(
        to=ProxyNode,
        related_name="ss_config",
        on_delete=models.CASCADE,
        primary_key=True,
        help_text="代理节点",
        verbose_name="代理节点",
    )
    method = models.CharField(
        "加密类型", default=settings.DEFAULT_METHOD, max_length=32, choices=c.METHOD_CHOICES
    )
    multi_user_port = models.IntegerField(
        "多用户端口", help_text="单端口多用户端口", null=True, blank=True
    )

    class Meta:
        verbose_name = "SS配置"
        verbose_name_plural = "SS配置"

    def __str__(self) -> str:
        return self.proxy_node.__str__() + "-配置"


class RelayNode(BaseNodeModel):

    CMCC = "移动"
    CUCC = "联通"
    CTCC = "电信"
    BGP = "BGP"
    ISP_TYPES = (
        (CMCC, "移动"),
        (CUCC, "联通"),
        (CTCC, "电信"),
        (BGP, "BGP"),
    )

    isp = models.CharField("ISP线路", max_length=64, choices=ISP_TYPES, default=BGP)

    class Meta:
        verbose_name = "中转节点"
        verbose_name_plural = "中转节点"

    def __str__(self) -> str:
        return self.name

    @property
    def api_endpoint(self):
        params = {"token": settings.TOKEN}
        return settings.HOST + f"/api/ehco_relay_config/{self.id}/?{urlencode(params)}"

    @classmethod
    def get_ip_list(cls):
        return [node.server for node in cls.objects.filter(enable=True)]


class RelayRule(BaseModel):

    proxy_node = models.ForeignKey(
        ProxyNode,
        on_delete=models.CASCADE,
        verbose_name="代理节点",
        related_name="relay_rules",
    )
    relay_node = models.ForeignKey(
        RelayNode,
        on_delete=models.CASCADE,
        verbose_name="中转节点",
        related_name="relay_rules",
    )

    relay_port = models.CharField("中转端口", max_length=64, blank=False, null=False)
    listen_type = models.CharField(
        "监听类型", max_length=64, choices=c.LISTEN_TYPES, default=c.LISTEN_RAW
    )
    transport_type = models.CharField(
        "传输类型", max_length=64, choices=c.TRANSPORT_TYPES, default=c.TRANSPORT_RAW
    )

    class Meta:
        verbose_name = "中转规则"
        verbose_name_plural = "中转规则"

    def __str__(self) -> str:
        return self.remark

    def to_dict_with_extra_info(self, user):
        data = model_to_dict(self)
        data["relay_link"] = self.get_user_relay_link(user)
        data["relay_host"] = self.relay_host
        data["remark"] = self.remark
        return data

    @property
    def relay_host(self):
        return self.relay_node.server

    @property
    def enable(self):
        return self.relay_node.enable and self.proxy_node.enable

    @property
    def remark(self):
        name = f"{self.relay_node.name}->{self.proxy_node.name}({self.proxy_node.node_type})"
        if self.proxy_node.enlarge_scale != Decimal(1.0):
            name += f"-{self.proxy_node.enlarge_scale}倍"
        return name


class NodeOnlineLog(BaseLogModel):

    proxy_node = models.ForeignKey(
        ProxyNode, on_delete=models.CASCADE, verbose_name="代理节点",
    )
    online_user_count = models.IntegerField(default=0, verbose_name="用户数")
    tcp_connections_count = models.IntegerField(default=0, verbose_name="tcp链接数")

    class Meta:
        verbose_name = "节点在线记录"
        verbose_name_plural = "节点在线记录"
        ordering = ["-created_at"]
        index_together = ["proxy_node", "created_at"]

    def __str__(self) -> str:
        return f"{self.proxy_node.name}节点在线记录"

    @classmethod
    def get_latest_log(cls, proxy_node):
        return cls.objects.filter(proxy_node=proxy_node).order_by("-created_at").first()

    @classmethod
    def get_latest_online_log_info(cls, proxy_node):
        data = {"online": False, "online_user_count": 0, "tcp_connections_count": 0}
        log = cls.get_latest_log(proxy_node)
        if log and log.online:
            data["online"] = log.online
            data.update(model_to_dict(log))
        return data

    @classmethod
    def get_all_node_online_user_count(cls):

        count = 0
        for node in ProxyNode.get_active_nodes():
            log = cls.get_latest_log(node.id)
            if log:
                count += log.online_user_count
        return count

    @property
    def online(self):
        return (
            utils.get_current_datetime().subtract(seconds=c.NODE_TIME_OUT)
            < self.created_at
        )


class UserTrafficLog(BaseLogModel):

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    proxy_node = models.ForeignKey(
        ProxyNode, on_delete=models.CASCADE, verbose_name="代理节点",
    )
    upload_traffic = models.BigIntegerField("上传流量", default=0)
    download_traffic = models.BigIntegerField("下载流量", default=0)

    class Meta:
        verbose_name = "用户流量记录"
        verbose_name_plural = "用户流量记录"
        ordering = ["-created_at"]
        index_together = ["user", "proxy_node", "created_at"]

    def __str__(self) -> str:
        return f"{self.proxy_node.name}用户流量记录"

    @property
    def total_traffic(self):
        return utils.traffic_format(self.download_traffic + self.upload_traffic)


class UserOnLineIpLog(BaseLogModel):

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    proxy_node = models.ForeignKey(
        ProxyNode, on_delete=models.CASCADE, verbose_name="代理节点",
    )
    ip = models.CharField(max_length=128, verbose_name="IP地址")

    class Meta:
        verbose_name = "用户在线IP记录"
        verbose_name_plural = "用户在线IP记录"
        ordering = ["-created_at"]
        index_together = ["user", "proxy_node", "created_at"]

    def __str__(self) -> str:
        return f"{self.proxy_node.name}用户在线IP记录"
