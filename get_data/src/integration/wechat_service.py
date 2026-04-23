# -*- coding: utf-8 -*-
"""
微信客服服务

对接外部客服系统，支持：
- 发送模板消息
- 查询用户列表
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import httpx

logger = logging.getLogger("integration.wechat")


class WeChatServiceConfig:
    """微信客服服务配置"""
    def __init__(self):
        from src.config import DATA_DIR
        # 外部客服API地址（由后端提供）
        self.api_base_url = "http://10.175.1.209:8103"  # 外部客服系统地址
        self.api_prefix = "/api/customer-service"
        self.timeout = 30.0

        # 默认模板ID（可在微信公众平台申请）
        self.default_template_id = ""


class WeChatUser:
    """微信用户信息"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.openid = data.get("openid", "")
        self.nickname = data.get("nickname", "")
        self.sex = data.get("sex", 0)
        self.city = data.get("city", "")
        self.province = data.get("province", "")
        self.country = data.get("country", "")
        self.head_img_url = data.get("headImgUrl", "")
        self.subscribe = data.get("subscribe", 0)
        self.subscribe_time = data.get("subscribeTime")
        self.last_interact_time = data.get("lastInteractTime")
        self.phone = data.get("phone", "")
        self.real_name = data.get("realName", "")
        self.unionid = data.get("unionid", "")

    @property
    def is_subscribed(self) -> bool:
        """是否已关注"""
        return self.subscribe == 1


class TemplateMessageResult:
    """模板消息发送结果"""
    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        self.success = errcode == 0


class WeChatService:
    """
    微信客服服务客户端

    对接外部客服系统API，支持发送模板消息和查询用户列表。
    """

    def __init__(self, config: WeChatServiceConfig = None):
        self.config = config or WeChatServiceConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端（懒加载）"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_base_url,
                timeout=self.config.timeout
            )
        return self._client

    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_template_message(
        self,
        openid: str,
        data: Dict[str, str],
        template_id: str = None,
        url: str = None,
        miniprogram_appid: str = None,
        miniprogram_pagepath: str = None
    ) -> TemplateMessageResult:
        """
        发送模板消息

        Args:
            openid: 用户openid
            data: 模板数据，key对应模板中的 {{xxx.DATA}} 参数名
            template_id: 模板消息ID（不传则使用默认）
            url: 点击跳转URL
            miniprogram_appid: 跳转小程序AppID
            miniprogram_pagepath: 跳转小程序页面路径

        Returns:
            TemplateMessageResult: 发送结果
        """
        if not openid:
            return TemplateMessageResult(400, "openid不能为空")
        if not data:
            return TemplateMessageResult(400, "data不能为空")

        payload = {
            "openid": openid,
            "data": data
        }

        if template_id:
            payload["templateId"] = template_id
        if url:
            payload["url"] = url
        if miniprogram_appid:
            payload["miniprogramAppid"] = miniprogram_appid
        if miniprogram_pagepath:
            payload["miniprogramPagepath"] = miniprogram_pagepath

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.config.api_prefix}/template/send",
                json=payload
            )
            result = response.json()

            errcode = result.get("errcode", -1)
            errmsg = result.get("errmsg", "未知错误")

            logger.info(f"发送模板消息结果: openid={openid}, errcode={errcode}, errmsg={errmsg}")
            return TemplateMessageResult(errcode, errmsg)

        except httpx.TimeoutException:
            logger.error(f"发送模板消息超时: openid={openid}")
            return TemplateMessageResult(-1, "请求超时")
        except Exception as e:
            logger.exception(f"发送模板消息异常: openid={openid}, error={e}")
            return TemplateMessageResult(-1, f"系统异常: {str(e)}")

    async def get_users(
        self,
        page: int = 1,
        size: int = 10,
        subscribe: int = None
    ) -> Dict[str, Any]:
        """
        分页查询用户列表

        Args:
            page: 页码（从1开始）
            size: 每页条数
            subscribe: 关注状态筛选（1=已关注，0=已取关，None=全部）

        Returns:
            分页结果，包含 users 列表
        """
        params = {"page": page, "size": size}
        if subscribe is not None:
            params["subscribe"] = subscribe

        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.config.api_prefix}/users",
                params=params
            )
            result = response.json()

            # 转换为标准分页格式
            records = result.get("records", [])
            users = [WeChatUser(r) for r in records]

            return {
                "users": users,
                "total": result.get("total", 0),
                "size": result.get("size", size),
                "current": result.get("current", page),
                "pages": result.get("pages", 1)
            }

        except httpx.TimeoutException:
            logger.error("查询用户列表超时")
            return {"users": [], "total": 0, "error": "请求超时"}
        except Exception as e:
            logger.exception(f"查询用户列表异常: {e}")
            return {"users": [], "total": 0, "error": str(e)}

    async def get_subscribed_users(self, page: int = 1, size: int = 100) -> List[WeChatUser]:
        """获取已关注用户列表"""
        result = await self.get_users(page=page, size=size, subscribe=1)
        return result.get("users", [])

    async def broadcast_tender_notification(
        self,
        users: List[WeChatUser],
        project_name: str,
        buyer_name: str,
        budget: str,
        publish_date: str,
        detail_url: str = None,
        template_id: str = None
    ) -> Dict[str, Any]:
        """
        广播招标通知给多个用户

        Args:
            users: 用户列表
            project_name: 项目名称
            buyer_name: 采购单位
            budget: 预算金额
            publish_date: 发布时间
            detail_url: 详情链接
            template_id: 模板ID

        Returns:
            发送结果统计
        """
        success_count = 0
        fail_count = 0
        errors = []

        for user in users:
            if not user.is_subscribed:
                continue

            result = await self.send_template_message(
                openid=user.openid,
                data={
                    "first": f"新招标项目：{project_name}",
                    "keyword1": buyer_name,
                    "keyword2": budget,
                    "keyword3": publish_date,
                    "remark": "点击查看详情，获取更多商业机会"
                },
                template_id=template_id or self.config.default_template_id,
                url=detail_url
            )

            if result.success:
                success_count += 1
            else:
                fail_count += 1
                errors.append({"openid": user.openid, "error": result.errmsg})

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(users),
            "errors": errors[:10]  # 最多返回10条错误
        }


# 全局单例
_wechat_service: Optional[WeChatService] = None


def get_wechat_service() -> WeChatService:
    """获取微信服务单例"""
    global _wechat_service
    if _wechat_service is None:
        _wechat_service = WeChatService()
    return _wechat_service
