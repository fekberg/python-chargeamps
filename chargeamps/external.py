"""Charge-Amps External API Client"""

import asyncio
import re
import time
from typing import List

import aiohttp
import jwt

from .base import (ChargeAmpsClient, ChargePoint, ChargePointConnectorSettings,
                   ChargePointStatus, ChargingSession)

API_BASE_URL = "https://ca-externalapi.azurewebsites.net"


class ChargeAmpsExternalClient(ChargeAmpsClient):

    def __init__(self, email: str, password: str, api_key: str, api_base_url: str = API_BASE_URL):
        self._email = email
        self._password = password
        self._api_key = api_key
        self._session = aiohttp.ClientSession(raise_for_status=True)
        self._headers = {}
        self._base_url = api_base_url
        self._ssl = False
        self._token = None
        self._token_expire = 0

    async def shutdown(self):
        await self._session.close()

    async def _ensure_token(self):
        if self._token_expire < time.time():
            response = await self._session.post(f"{self._base_url}/api/v3/auth/login",
                                                ssl=self._ssl,
                                                headers={'apiKey': self._api_key},
                                                json={'email': self._email, 'password': self._password})
            self._token = (await response.json())['token']
            token_payload = jwt.decode(self._token, verify=False)
            self._token_expire = token_payload.get('exp', 0)
            self._headers['Authorization'] = f"Bearer {self._token}"

    async def _post(self, path, **kwargs):
        await self._ensure_token()
        headers = kwargs.pop('headers', self._headers)
        return await self._session.post(f"{self._base_url}/{path}",
                                        ssl=self._ssl,
                                        headers=headers, **kwargs)

    async def _get(self, path, **kwargs):
        await self._ensure_token()
        headers = kwargs.pop('headers', self._headers)
        return await self._session.get(f"{self._base_url}/{path}",
                                     ssl=self._ssl,
                                     headers=headers, **kwargs)

    async def _put(self, path, **kwargs):
        await self._ensure_token()
        headers = kwargs.pop('headers', self._headers)
        return await self._session.put(f"{self._base_url}/{path}",
                                       ssl=self._ssl,
                                       headers=headers, **kwargs)


    async def get_chargepoints(self) -> List[ChargePoint]:
        """Get all owned chargepoints"""
        request_uri = '/api/v3/chargepoints/owned'
        response = await self._get(request_uri)
        res = []
        for chargepoint in await response.json():
            res.append(ChargePoint.from_dict(chargepoint))
        return res

    async def get_chargingsessions(self, charge_point_id: str) -> List[ChargingSession]:
        """Get all charging sessions"""
        request_uri = f'/api/v3/chargepoints/{charge_point_id}/chargingsessions'
        response = await self._get(request_uri)
        res = []
        for session in await response.json():
            for key in ['startTime', 'endTime']:
                if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d\d$', session[key]):
                    session[key] += '0'
            res.append(ChargingSession.from_dict(session))
        return res

    async def get_chargepoint_status(self, charge_point_id: str) -> ChargePointStatus:
        """Get charge point status"""
        request_uri = f'/api/v3/chargepoints/{charge_point_id}/status'
        response = await self._get(request_uri)
        return ChargePointStatus.from_dict(await response.json())

    async def get_chargepoint_connector_settings(self, charge_point_id: str, connector_id: str) -> ChargePointConnectorSettings:
        """Get all owned chargepoints"""
        request_uri = f'/api/v3/chargepoints/{charge_point_id}/connectors/{connector_id}/settings'
        response = await self._get(request_uri)
        return ChargePointConnectorSettings.from_dict(await response.json())

    async def set_chargepoint_connector_settings(self, settings: ChargePointConnectorSettings) -> None:
        """Get all owned chargepoints"""
        payload = settings.to_dict()
        charge_point_id = settings.charge_point_id
        connector_id = settings.connector_id
        request_uri = f'/api/v3/chargepoints/{charge_point_id}/connectors/{connector_id}/settings'
        await self._put(request_uri, json=payload)
