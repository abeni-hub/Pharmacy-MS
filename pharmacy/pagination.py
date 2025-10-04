# your_app/pagination.py
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class CustomPagination(PageNumberPagination):
    page_size_query_param = 'page_size'   # allow dynamic ?page_size=20
    max_page_size = 100                   # prevent abuse
    page_query_param = 'pageNumber'       # frontend expects pageNumber

    def get_paginated_response(self, data):
        return Response({
            "data": data,
            "pagination": {
                "pageNumber": self.page.number,
                "pageSize": self.page.paginator.per_page,
                "totalItems": self.page.paginator.count,
                "totalPages": self.page.paginator.num_pages,
                "hasNextPage": self.page.has_next(),
                "hasPreviousPage": self.page.has_previous(),
            }
        })
